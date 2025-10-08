from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]
REGION = os.environ.get("CONNECT_REGION", "us-west-2")

connect = CONNECT

def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    }

def respond(status_code: int, payload: dict):
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(payload),
    }

# ---- helpers ---------------------------------------------------------------

_STATUS_MAP = {
    "AccessDeniedException": 403,
    "InvalidRequestException": 400,
    "InvalidParameterException": 400,
    "ResourceNotFoundException": 404,
    "ThrottlingException": 429,
    "LimitExceededException": 429,
    "InternalServiceException": 502,
}

def _level_to_int(level):
    try:
        # API accepts number (documented as float); allow "2", 2, 2.0 etc.
        n = int(float(level))
        if n < 1 or n > 5:
            return None
        return n
    except Exception:
        return None

def _norm_items(items, require_level: bool):
    """
    Convert UI items to AWS shapes.
    items: [{attributeName, attributeValue, level?}]
    Returns (valid_list, invalid_list_with_reason)
    """
    valid = []
    invalid = []

    if not isinstance(items, list):
        return [], [{"item": items, "reason": "Must be a list"}]

    for it in items:
        name = (it or {}).get("attributeName")
        value = (it or {}).get("attributeValue")
        lvl = (it or {}).get("level", None)

        if not isinstance(name, str) or not name.strip():
            invalid.append({"item": it, "reason": "attributeName required"})
            continue
        if not isinstance(value, str) or not value.strip():
            invalid.append({"item": it, "reason": "attributeValue required"})
            continue

        out = {
            "AttributeName": name.strip(),
            "AttributeValue": value.strip()
        }

        if require_level:
            lvl_int = _level_to_int(lvl)
            if lvl_int is None:
                invalid.append({"item": it, "reason": "level must be 1..5"})
                continue
            out["Level"] = lvl_int

        valid.append(out)

    return valid, invalid

def _call_with_catch(fn, **kwargs):
    try:
        fn(**kwargs)
        return {"ok": True, "status": 200, "error": None}
    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        req_id = e.response.get("ResponseMetadata", {}).get("RequestId")
        status = _STATUS_MAP.get(code, 502)
        logger.warning(f"{fn.__name__} failed [{code}] {msg} (requestId={req_id})")
        return {
            "ok": False,
            "status": status,
            "error": {"code": code, "message": msg, "requestId": req_id}
        }
    except Exception as e:
        logger.exception(f"Unhandled error in {fn.__name__}")
        return {
            "ok": False,
            "status": 500,
            "error": {"code": "InternalServerError", "message": str(e)}
        }

# ---- main entry ------------------------------------------------------------

def handle_post_user_proficiencies(body: dict):
    """
    Expected body example:
    {
      "username": "allison.bicker",
      "user_id": "745b7082-0c31-4a4d-b94e-9ff0a4e2968c",
      "associate":   [ { "attributeName": "skill_name", "attributeValue": "billing", "level": 3 } ],
      "update":      [ { "attributeName": "skill_name", "attributeValue": "outage",  "level": 2 } ],
      "dissociate":  [ { "attributeName": "skill_name", "attributeValue": "legacy" } ]
    }
    """
    body = body or {}
    user_id = body.get("user_id")
    username = body.get("username")

    if not user_id or not isinstance(user_id, str):
        return respond(400, {"error": "BadRequest", "message": "Field 'user_id' is required."})

    # Normalize per section
    associate_valid, associate_invalid = _norm_items(body.get("associate", []), require_level=True)
    update_valid, update_invalid       = _norm_items(body.get("update", []),    require_level=True)
    dissoc_valid, dissoc_invalid       = _norm_items(body.get("dissociate", []), require_level=False)

    # Run calls in order: associate -> update -> disassociate
    results = {
        "associate": {"attempted": len(associate_valid), "result": None, "invalid": associate_invalid},
        "update":    {"attempted": len(update_valid),    "result": None, "invalid": update_invalid},
        "dissociate":{"attempted": len(dissoc_valid),    "result": None, "invalid": dissoc_invalid},
    }

    # If nothing to do and nothing invalid, short-circuit
    if results["associate"]["attempted"] == 0 and results["update"]["attempted"] == 0 and results["dissociate"]["attempted"] == 0:
        if not (associate_invalid or update_invalid or dissoc_invalid):
            return respond(400, {"error": "BadRequest", "message": "Nothing to do. Provide at least one of associate/update/dissociate."})

    # 1) Associate
    if associate_valid:
        results["associate"]["result"] = _call_with_catch(
            connect.associate_user_proficiencies,
            InstanceId=INSTANCE_ID,
            UserId=user_id,
            UserProficiencies=associate_valid
        )
    else:
        results["associate"]["result"] = {"ok": True, "status": 200, "skipped": True}

    # 2) Update
    if update_valid:
        results["update"]["result"] = _call_with_catch(
            connect.update_user_proficiencies,
            InstanceId=INSTANCE_ID,
            UserId=user_id,
            UserProficiencies=update_valid
        )
    else:
        results["update"]["result"] = {"ok": True, "status": 200, "skipped": True}

    # 3) Disassociate
    if dissoc_valid:
        results["dissociate"]["result"] = _call_with_catch(
            connect.disassociate_user_proficiencies,
            InstanceId=INSTANCE_ID,
            UserId=user_id,
            UserProficiencies=dissoc_valid
        )
    else:
        results["dissociate"]["result"] = {"ok": True, "status": 200, "skipped": True}

    # Decide top-level status:
    worst_status = max(r["result"]["status"] for r in results.values() if r["result"])
    return respond(200 if all(r["result"]["ok"] for r in results.values()) else worst_status, {
        "instanceId": INSTANCE_ID,
        "userId": user_id,
        "username": username,
        "results": results
    })
