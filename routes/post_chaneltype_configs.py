from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import json
import logging
import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = DDB
table = dynamodb.Table("teco-dynamodb-business-group-configs-us-east-1-dev")

# ---------- HTTP helpers ----------
def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    }

def respond(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": _cors_headers(),
        "body": json.dumps(payload),
    }

# ---------- Attribute name mapping (only where '#' truly exists in DB) ----------
DB_TO_UI = {
    "config_type#channel_type": "config_type_channel_type",
    "broadcast_message#en": "broadcast_message_en",
    "broadcast_message#es": "broadcast_message_es",
    "first_hold_message#en": "first_hold_message_en",
    "first_hold_message#es": "first_hold_message_es",
    "initial_queue_message#en": "initial_queue_message_en",
    "initial_queue_message#es": "initial_queue_message_es",
    "out_of_service_message#en": "out_of_service_message_en",
    "out_of_service_message#es": "out_of_service_message_es",
    "second_hold_message#en": "second_hold_message_en",
    "second_hold_message#es": "second_hold_message_es",
    "voicemail_prompt#en": "voicemail_prompt_en",
}
UI_TO_DB = {v: k for k, v in DB_TO_UI.items()}

REQUEST_ONLY_KEYS = {"action", "businessGroup", "channelType"}

def _to_ui_item(item: dict) -> dict:
    out = {}
    for k, v in item.items():
        out[DB_TO_UI.get(k, k)] = v
    return out

def _from_ui_item(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        if k in REQUEST_ONLY_KEYS:
            continue
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        out[UI_TO_DB.get(k, k)] = v
    return out

# ---------- Main handler ----------
def handle_chaneltype_configs(body):
    """
    Supports: list | create | update | delete

    PK: business_group_id
    SK: config_type#channel_type   (alias in UI: config_type_channel_type)
    """
    try:
        logger.info("Incoming body: %s", body)

        action = body.get("action", "list")
        business_group = body.get("businessGroup") or body.get("business_group_id")
        channel_type = body.get("channelType")

        # -------- LIST --------
        if action == "list":
            if not business_group or channel_type is None:
                return respond(400, {"error": "Both 'businessGroup' and 'channelType' are required"})

            # 1) Query by PK only (no FilterExpression on the SK!)
            logger.info("Listing configs for bg=%s, channelType=%s", business_group, channel_type)
            result = table.query(
                KeyConditionExpression=Key("business_group_id").eq(business_group)
            )
            items = result.get("Items", [])

            # 2) Pagination
            while "LastEvaluatedKey" in result:
                result = table.query(
                    KeyConditionExpression=Key("business_group_id").eq(business_group),
                    ExclusiveStartKey=result["LastEvaluatedKey"],
                )
                items.extend(result.get("Items", []))

            # 3) In-code filter by SK suffix
            def _is_channel_match(sk: str, ch: str) -> bool:
                if not isinstance(sk, str):
                    return False
                if ch == "generic":
                    # include only voice/chat rows
                    return sk.endswith("#voice") or sk.endswith("#chat")
                else:
                    return sk.endswith(f"#{ch}")

            filtered = [it for it in items if _is_channel_match(it.get("config_type#channel_type", ""), channel_type)]

            logger.info("List returned %d items for bg=%s, channelType=%s", len(filtered), business_group, channel_type)
            return respond(200, {"results": [_to_ui_item(it) for it in filtered]})

        # -------- CREATE --------
        elif action == "create":
            logger.info("Creating config")
            item = _from_ui_item(body)

            pk = item.get("business_group_id")
            sk = item.get("config_type#channel_type")
            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'business_group_id' and 'config_type#channel_type' are required"})

            table.put_item(Item=item)
            return respond(200, {"message": "Configuration created successfully"})

        # -------- UPDATE --------
        elif action == "update":
            logger.info("Updating config")
            converted = _from_ui_item(body)

            pk = converted.get("business_group_id")
            sk = converted.get("config_type#channel_type")
            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'business_group_id' and 'config_type#channel_type' are required"})

            to_update = {k: v for k, v in converted.items() if k not in ("business_group_id", "config_type#channel_type")}
            if not to_update:
                return respond(400, {"error": "No attributes provided for update"})

            parts, names, values = [], {}, {}
            for i, (k, v) in enumerate(to_update.items()):
                nk, nv = f"#n{i}", f":v{i}"
                parts.append(f"{nk} = {nv}")
                names[nk] = k
                values[nv] = v

            update_expr = "SET " + ", ".join(parts)

            table.update_item(
                Key={"business_group_id": pk, "config_type#channel_type": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
            )
            return respond(200, {"message": "Configuration updated successfully"})

        # -------- DELETE --------
        elif action == "delete":
            logger.info("Deleting config")
            sk = body.get("config_type#channel_type") or body.get("config_type_channel_type")
            pk = body.get("business_group_id")
            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'business_group_id' and 'config_type#channel_type' are required"})

            table.delete_item(Key={"business_group_id": pk, "config_type#channel_type": sk})
            return respond(200, {"message": "Configuration deleted successfully"})

        else:
            return respond(400, {"error": f"Unsupported action '{action}'"})

    except Exception as e:
        logger.exception("Error processing config request")
        return respond(500, {"error": str(e)})
