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
table = dynamodb.Table("teco-dynamodb-callflow-prompts-us-east-1-dev")


# ----------------- Helpers -----------------
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


# Keys that should NEVER be written to DynamoDB
REQUEST_ONLY_KEYS = {"action", "businessGroup", "channelType"}

def _clean_for_put(item: dict) -> dict:
    """
    Return a copy of `item` with:
      - request-only keys removed (e.g. 'action', 'businessGroup', 'channelType')
      - keys with None or "" removed (optional hygiene)
    """
    cleaned = {}
    for k, v in item.items():
        if k in REQUEST_ONLY_KEYS:
            continue
        if v is None or (isinstance(v, str) and v.strip() == ""):
            # Skip empty values to avoid sparse/meaningless attributes
            continue
        cleaned[k] = v
    return cleaned


def handle_chaneltype_prompts(body):
    """
    Supports actions: list | create | update | delete
    PK: callflow_name
    SK: prompt_id
    """

    try:
        logger.info("Incoming request: %s", body)

        action = body.get("action", "list")
        business_group = body.get("businessGroup") or body.get("business_group_id")
        channel_type   = body.get("channelType")

        # ---------- LIST ----------
        if action == "list":
            if not business_group or not channel_type:
                return respond(400, {"error": "Both 'businessGroup' and 'channelType' are required"})

            logger.info("Listing prompts for bg=%s, channel=%s", business_group, channel_type)

            if channel_type == "generic":
                result = table.query(
                    IndexName="business_group_id-channel-index",
                    KeyConditionExpression=Key("business_group_id").eq(business_group)
                )
            else:
                result = table.query(
                    IndexName="business_group_id-channel-index",
                    KeyConditionExpression=Key("business_group_id").eq(business_group) &
                                           Key("channel").eq(channel_type)
                )

            items = result.get("Items", [])
            while "LastEvaluatedKey" in result:
                result = table.query(
                    IndexName="business_group_id-channel-index",
                    KeyConditionExpression=Key("business_group_id").eq(business_group) if channel_type == "generic"
                                             else Key("business_group_id").eq(business_group) &
                                                  Key("channel").eq(channel_type),
                    ExclusiveStartKey=result["LastEvaluatedKey"]
                )
                items.extend(result.get("Items", []))

            # No attribute names have '#', but we keep parity with your UI approach:
            clean_items = [{k.replace("#", "_"): v for k, v in item.items()} for item in items]
            return respond(200, {"results": clean_items})

        # ---------- CREATE ----------
        elif action == "create":
            logger.info("Creating prompt item")
            # Strip request-only keys (e.g., 'action') before writing
            item = _clean_for_put(body)

            # Validate PK/SK
            if not item.get("callflow_name") or not item.get("prompt_id"):
                return respond(400, {"error": "Missing primary keys: 'callflow_name' and 'prompt_id' are required"})

            table.put_item(Item=item)
            return respond(200, {"message": "Prompt created successfully"})

        # ---------- UPDATE ----------
        elif action == "update":
            logger.info("Updating prompt item")
            pk = body.get("callflow_name")
            sk = body.get("prompt_id")

            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'callflow_name' and 'prompt_id' are required"})

            # Sanitize input and remove PK/SK from update set
            cleaned = _clean_for_put(body)
            # Ensure PK/SK remain present in Key but not in update attrs
            cleaned.pop("callflow_name", None)
            cleaned.pop("prompt_id", None)

            if not cleaned:
                return respond(400, {"error": "No attributes provided for update"})

            # Safe placeholders so we never collide with reserved words
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

            table.update_item(
                Key={"callflow_name": pk, "prompt_id": sk},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_values
            )

            return respond(200, {"message": "Prompt updated successfully"})

        # ---------- DELETE ----------
        elif action == "delete":
            logger.info("Deleting prompt item")
            pk = body.get("callflow_name")
            sk = body.get("prompt_id")

            if not pk or not sk:
                return respond(400, {"error": "Missing primary keys: 'callflow_name' and 'prompt_id' are required"})

            table.delete_item(Key={"callflow_name": pk, "prompt_id": sk})
            return respond(200, {"message": "Prompt deleted successfully"})

        else:
            return respond(400, {"error": f"Unsupported action '{action}'"})

    except Exception as e:
        logger.exception("Error in Lambda")
        return respond(500, {"error": str(e)})
