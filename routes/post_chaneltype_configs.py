from utils.aws_clients import ddb as DDB, table
from utils.logger import get_logger
from utils.http import respond
from boto3.dynamodb.conditions import Key
import os

# ---------------------------------------------------------------------------
# Logging & AWS Clients
# ---------------------------------------------------------------------------
logger = get_logger(__name__)
dynamodb = DDB

# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------
CONFIGS_TABLE_NAME = os.environ["DDB_TABLE_TECO_DYNAMODB_BUSINESS_GROUP_CONFIGS_US_EAST_1_DEV"]
configs_table = dynamodb.Table(CONFIGS_TABLE_NAME)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _to_ui_item(item: dict) -> dict:
    """Convert DynamoDB attributes to UI-safe names."""
    return {DB_TO_UI.get(k, k): v for k, v in item.items()}


def _from_ui_item(data: dict) -> dict:
    """Convert UI attribute names back to DynamoDB schema."""
    out = {}
    for k, v in data.items():
        if k in REQUEST_ONLY_KEYS:
            continue
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        out[UI_TO_DB.get(k, k)] = v
    return out


# ---------------------------------------------------------------------------
# Main Handler
# ---------------------------------------------------------------------------
def handle_chaneltype_configs(body: dict):

    try:
        logger.info(f"[REQUEST] Incoming body: {body}")
        action = body.get("action", "list")
        business_group = body.get("businessGroup") or body.get("business_group_id")
        channel_type = body.get("channelType")

        # ---------- LIST ----------
        if action == "list":
            if not business_group or channel_type is None:
                return respond(400, {"error": "Both 'businessGroup' and 'channelType' are required"})

            logger.info(f"[LIST] Fetching configs for BG={business_group}, channelType={channel_type}")

            result = configs_table.query(
                KeyConditionExpression=Key("business_group_id").eq(business_group)
            )
            items = result.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in result:
                result = configs_table.query(
                    KeyConditionExpression=Key("business_group_id").eq(business_group),
                    ExclusiveStartKey=result["LastEvaluatedKey"]
                )
                items.extend(result.get("Items", []))

            # Filter by channel type
            def _is_channel_match(sk: str, ch: str) -> bool:
                if not isinstance(sk, str):
                    return False
                if ch == "generic":
                    return sk.endswith("#voice") or sk.endswith("#chat")
                return sk.endswith(f"#{ch}")

            filtered = [it for it in items if _is_channel_match(it.get("config_type#channel_type", ""), channel_type)]
            logger.info(f"[LIST] Returned {len(filtered)} configs for BG={business_group}")

            return respond(200, {"results": [_to_ui_item(it) for it in filtered]})

        # ---------- CREATE ----------
        elif action == "create":
            item = _from_ui_item(body)
            pk = item.get("business_group_id")
            sk = item.get("config_type#channel_type")

            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'business_group_id' and 'config_type#channel_type'"})

            configs_table.put_item(Item=item)
            logger.info(f"[CREATE] Created config BG={pk}, SK={sk}")
            return respond(200, {"message": "Configuration created successfully"})

        # ---------- UPDATE ----------
        elif action == "update":
            converted = _from_ui_item(body)
            pk = converted.get("business_group_id")
            sk = converted.get("config_type#channel_type")

            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'business_group_id' and 'config_type#channel_type'"})

            # Build update expression
            to_update = {k: v for k, v in converted.items() if k not in ("business_group_id", "config_type#channel_type")}
            if not to_update:
                return respond(400, {"error": "No attributes provided for update"})

            parts, names, values = [], {}, {}
            for i, (k, v) in enumerate(to_update.items()):
                nk, nv = f"#n{i}", f":v{i}"
                parts.append(f"{nk} = {nv}")
                names[nk] = k
                values[nv] = v

            configs_table.update_item(
                Key={"business_group_id": pk, "config_type#channel_type": sk},
                UpdateExpression="SET " + ", ".join(parts),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values
            )

            logger.info(f"[UPDATE] Updated config BG={pk}, SK={sk}")
            return respond(200, {"message": "Configuration updated successfully"})

        # ---------- DELETE ----------
        elif action == "delete":
            pk = body.get("business_group_id")
            sk = body.get("config_type#channel_type") or body.get("config_type_channel_type")

            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'business_group_id' and 'config_type#channel_type'"})

            configs_table.delete_item(Key={"business_group_id": pk, "config_type#channel_type": sk})
            logger.info(f"[DELETE] Deleted config BG={pk}, SK={sk}")
            return respond(200, {"message": "Configuration deleted successfully"})

        # ---------- INVALID ----------
        else:
            logger.warning(f"[INVALID] Unsupported action: {action}")
            return respond(400, {"error": f"Unsupported action '{action}'"})

    except Exception as e:
        logger.exception("[ERROR] Unhandled exception in handle_chaneltype_configs")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
