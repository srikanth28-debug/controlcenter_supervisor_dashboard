from utils.aws_clients import connect
from utils.logger import get_logger
from utils.http import respond
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timezone
import os, json, time

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
INSTANCE_ID = os.getenv("CONNECT_INSTANCE_ID")
REGION = os.getenv("CONNECT_REGION", "us-east-1")

CONNECT = connect
_CACHE = {"data": None, "timestamp": 0, "ttl": 300}  # 5-minute shared cache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _iso(dt):
    if not dt:
        return None
    try:
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return str(dt)

def _paginate_list_predefined_attributes(instance_id):
    paginator = CONNECT.get_paginator("list_predefined_attributes")
    for page in paginator.paginate(InstanceId=instance_id):
        for s in page.get("PredefinedAttributeSummaryList", []):
            yield s

def _describe_attribute(instance_id, name):
    resp = CONNECT.describe_predefined_attribute(InstanceId=instance_id, Name=name)
    pa = resp.get("PredefinedAttribute", {}) or {}
    values_obj = pa.get("Values") or {}
    values = values_obj.get("StringList", [])
    return {
        "name": pa.get("Name") or name,
        "values": values,
        "lastModifiedTime": _iso(pa.get("LastModifiedTime")),
        "lastModifiedRegion": pa.get("LastModifiedRegion"),
    }

# ---------------------------------------------------------------------------
# Optimized handler
# ---------------------------------------------------------------------------
def handle_get_predefined_attributes():
    try:
        now = time.time()
        if _CACHE["data"] and (now - _CACHE["timestamp"] < _CACHE["ttl"]):
            logger.info("[CACHE] Returning cached predefined attributes")
            return respond(200, _CACHE["data"])

        logger.info(f"[GET] Fetching predefined attributes for instance {INSTANCE_ID}")

        summaries = list(_paginate_list_predefined_attributes(INSTANCE_ID))
        attributes, value_map = [], {}

        # ---- Parallel describe calls ----
        def fetch_detail(summary):
            name = summary.get("Name")
            if not name:
                return None
            try:
                return _describe_attribute(INSTANCE_ID, name)
            except Exception as e:
                logger.warning(f"Describe failed for {name}: {e}")
                return None

        # 10-15 concurrent threads is safe for Connect API
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(fetch_detail, s) for s in summaries]
            for f in as_completed(futures):
                d = f.result()
                if not d:
                    continue
                attributes.append({"name": d["name"], "values": d["values"]})
                value_map[d["name"]] = d["values"]

        # ---- Sort + prepare response ----
        attributes.sort(key=lambda a: a["name"].lower())
        attribute_options = [a["name"] for a in attributes]

        response_body = {
            "attributeOptions": attribute_options,
            "valueOptionsByAttribute": value_map,
        }

        # ---- Update cache ----
        _CACHE.update({"data": response_body, "timestamp": now})

        logger.info(f"[SUCCESS] Returned {len(attribute_options)} predefined attributes.")
        return respond(200, response_body)

    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code", "ClientError")
        msg = err.get("Message", str(e))
        logger.warning(f"[AWS ERROR] {code}: {msg}")
        return respond(502, {"error": code, "message": msg})

    except Exception as e:
        logger.exception("[UNHANDLED ERROR] While fetching predefined attributes")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
