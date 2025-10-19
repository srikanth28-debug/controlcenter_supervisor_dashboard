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
PROMPTS_TABLE_NAME = os.environ["DDB_TABLE_TECO_DYNAMODB_CALLFLOW_PROMPTS_US_EAST_1_DEV"]
prompts_table = dynamodb.Table(PROMPTS_TABLE_NAME)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REQUEST_ONLY_KEYS = {"action", "businessGroup", "channelType"}

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def _clean_for_put(item: dict) -> dict:
    """
    Remove non-persistent or empty fields from an item before writing to DynamoDB.
    """
    cleaned = {}
    for k, v in item.items():
        if k in REQUEST_ONLY_KEYS:
            continue
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        cleaned[k] = v
    return cleaned


# ---------------------------------------------------------------------------
# Main Handler
# ---------------------------------------------------------------------------
def handle_chaneltype_prompts(body: dict):

    try:
        logger.info(f"[REQUEST] Incoming body: {body}")

        action = body.get("action", "list")
        business_group = body.get("businessGroup") or body.get("business_group_id")
        channel_type = body.get("channelType")

        # ---------- LIST ----------
        if action == "list":
            if not business_group or not channel_type:
                return respond(400, {"error": "Both 'businessGroup' and 'channelType' are required"})

            logger.info(f"[LIST] Fetching prompts for BG={business_group}, channelType={channel_type}")

            # Query using GSI
            if channel_type == "generic":
                result = prompts_table.query(
                    IndexName="business_group_id-channel-index",
                    KeyConditionExpression=Key("business_group_id").eq(business_group)
                )
            else:
                result = prompts_table.query(
                    IndexName="business_group_id-channel-index",
                    KeyConditionExpression=Key("business_group_id").eq(business_group)
                                         & Key("channel").eq(channel_type)
                )

            items = result.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in result:
                result = prompts_table.query(
                    IndexName="business_group_id-channel-index",
                    KeyConditionExpression=(
                        Key("business_group_id").eq(business_group)
                        if channel_type == "generic"
                        else Key("business_group_id").eq(business_group)
                             & Key("channel").eq(channel_type)
                    ),
                    ExclusiveStartKey=result["LastEvaluatedKey"]
                )
                items.extend(result.get("Items", []))

            # Sanitize keys for frontend compatibility
            clean_items = [{k.replace("#", "_"): v for k, v in item.items()} for item in items]
            logger.info(f"[LIST] Fetched {len(clean_items)} prompt records")

            return respond(200, {"results": clean_items})

        # ---------- CREATE ----------
        elif action == "create":
            logger.info("[CREATE] Creating new prompt record")
            item = _clean_for_put(body)

            if not item.get("callflow_name") or not item.get("prompt_id"):
                return respond(400, {"error": "Missing primary keys: 'callflow_name' and 'prompt_id' are required"})

            prompts_table.put_item(Item=item)
            logger.info(f"[CREATE] Prompt created: {item.get('callflow_name')} - {item.get('prompt_id')}")
            return respond(200, {"message": "Prompt created successfully"})

        # ---------- UPDATE ----------
        elif action == "update":
            pk = body.get("callflow_name")
            sk = body.get("prompt_id")

            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'callflow_name' and 'prompt_id' are required"})

            cleaned = _clean_for_put(body)
            cleaned.pop("callflow_name", None)
            cleaned.pop("prompt_id", None)

            if not cleaned:
                return respond(400, {"error": "No attributes provided for update"})

            # Build expression safely
            update_parts = []
            expr_attr_names = {}
            expr_attr_values = {}
            for i, (k, v) in enumerate(cleaned.items()):
                name_ph = f"#n{i}"
                value_ph = f":v{i}"
                update_parts.append(f"{name_ph} = {value_ph}")
                expr_attr_names[name_ph] = k
                expr_attr_values[value_ph] = v

            update_expr = "SET " + ", ".join(update_parts)

            prompts_table.update_item(
                Key={"callflow_name": pk, "prompt_id": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values
            )

            logger.info(f"[UPDATE] Prompt updated: {pk} - {sk}")
            return respond(200, {"message": "Prompt updated successfully"})

        # ---------- DELETE ----------
        elif action == "delete":
            pk = body.get("callflow_name")
            sk = body.get("prompt_id")

            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'callflow_name' and 'prompt_id' are required"})

            prompts_table.delete_item(Key={"callflow_name": pk, "prompt_id": sk})
            logger.info(f"[DELETE] Prompt deleted: {pk} - {sk}")
            return respond(200, {"message": "Prompt deleted successfully"})

        # ---------- INVALID ----------
        else:
            logger.warning(f"[INVALID] Unsupported action: {action}")
            return respond(400, {"error": f"Unsupported action '{action}'"})

    except Exception as e:
        logger.exception("[ERROR] Unhandled exception in handle_chaneltype_prompts")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
