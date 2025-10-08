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
        n = int(float(level))
        return n if 1 <= n <= 5 else None
    except Exception:
        return None

def _norm_items(items, require_level: bool):
    """Normalize [{attributeName, attributeValue, level?}] -> AWS shapes."""
    valid, invalid = [], []
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

def _process_single_user(u: dict):
    user_id = (u or {}).get("user_id")
    username = (u or {}).get("username")

    if not user_id or not isinstance(user_id, str):
        return {
            "username": username,
            "userId": user_id,
            "status": 400,
            "overallOk": False,
            "error": {"code": "BadRequest", "message": "Field 'user_id' is required."}
        }

    assoc_valid, assoc_invalid = _norm_items(u.get("associate", []), require_level=True)
    upd_valid,   upd_invalid   = _norm_items(u.get("update", []),    require_level=True)
    dis_valid,   dis_invalid   = _norm_items(u.get("dissociate", []), require_level=False)

    results = {
        "associate": {"attempted": len(assoc_valid), "invalid": assoc_invalid, "result": None},
        "update":    {"attempted": len(upd_valid),   "invalid": upd_invalid,   "result": None},
        "dissociate":{"attempted": len(dis_valid),   "invalid": dis_invalid,   "result": None},
    }

    # 1) Associate
    if assoc_valid:
        results["associate"]["result"] = _call_with_catch(
            connect.associate_user_proficiencies,
            InstanceId=INSTANCE_ID,
            UserId=user_id,
            UserProficiencies=assoc_valid
        )
    else:
        results["associate"]["result"] = {"ok": True, "status": 200, "skipped": True}

    # 2) Update
    if upd_valid:
        results["update"]["result"] = _call_with_catch(
            connect.update_user_proficiencies,
            InstanceId=INSTANCE_ID,
            UserId=user_id,
            UserProficiencies=upd_valid
        )
    else:
        results["update"]["result"] = {"ok": True, "status": 200, "skipped": True}

    # 3) Disassociate
    if dis_valid:
        results["dissociate"]["result"] = _call_with_catch(
            connect.disassociate_user_proficiencies,
            InstanceId=INSTANCE_ID,
            UserId=user_id,
            UserProficiencies=dis_valid
        )
    else:
        results["dissociate"]["result"] = {"ok": True, "status": 200, "skipped": True}

    overall_ok = all(r["result"]["ok"] for r in results.values())
    worst_status = max(r["result"]["status"] for r in results.values())

    return {
        "username": username,
        "userId": user_id,
        "overallOk": overall_ok,
        "status": 200 if overall_ok else worst_status,
        "results": results
    }

def handle_post_user_proficiencies_bulk(body: dict):
    """
    Expected body:
    {
      "users": [
        {
          "username": "...",
          "user_id": "...",
          "associate":   [{ "attributeName": "...", "attributeValue": "...", "level": 1 }],
          "update":      [{ "attributeName": "...", "attributeValue": "...", "level": 2 }],
          "dissociate":  [{ "attributeName": "...", "attributeValue": "..." }]
        },
        ...
      ]
    }
    """
    users = (body or {}).get("users", [])
    if not isinstance(users, list) or len(users) == 0:
        return respond(400, {"error": "BadRequest", "message": "Field 'users' (non-empty array) is required."})

    per_user = [_process_single_user(u) for u in users]

    # Determine overall status (worst of all)
    worst = max(u["status"] for u in per_user) if per_user else 200
    overall_ok = all(u["overallOk"] for u in per_user)

    return respond(200 if overall_ok else worst, {
        "instanceId": INSTANCE_ID,
        "count": len(per_user),
        "results": per_user
    })
