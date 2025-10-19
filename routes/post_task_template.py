from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond, cors_headers
import json
import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---- ENV CONFIG ----
INSTANCE_ID       = os.environ.get("CONNECT_INSTANCE_ID")
REGION            = os.environ.get("CONNECT_REGION", "us-west-2")
QUICK_CONNECT_ID  = os.environ.get("QUICK_CONNECT_ID", "b96ec20b-10fe-4521-9a8b-e329f65e0706")  # change as needed
LOCAL_TZ          = os.environ.get("LOCAL_TZ", "America/Toronto")  # interpret incoming date/time in this tz

connect = CONNECT

def _resp(status, payload):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
            "Access-Control-Allow-Headers": "Content-Type,Authorization"
        },
        "body": json.dumps(payload)
    }

def _field_value(fields, *candidates):
    
    name_map  = {str(f.get("name", "")).strip().lower(): f.get("value") for f in fields}
    label_map = {str(f.get("label", "")).strip().lower(): f.get("value") for f in fields}
    for cand in candidates:
        key = str(cand).strip().lower()
        if key in name_map and name_map[key] is not None:
            return name_map[key]
        if key in label_map and label_map[key] is not None:
            return label_map[key]
    return None

def _build_scheduled_time(fields):
    """
    Combine date (YYYY-MM-DD) and time (HH:MM) from fields into epoch seconds.
    Returns an int epoch or None if inputs are missing/invalid.
    """
    date_str = _field_value(fields, "scheduleDateTime", "schedule date/time", "date")
    time_str = _field_value(fields, "scheduleTime", "schedule time", "time")

    if not date_str or not time_str:
        return None

    try:
        tz = ZoneInfo(LOCAL_TZ)
        # Accept "HH:MM" or "HH:MM:SS"
        parts = [int(x) for x in time_str.split(":")]
        hour, minute = parts[0], parts[1]
        second = parts[2] if len(parts) > 2 else 0

        dt_local = datetime.strptime(date_str, "%Y-%m-%d").replace(
            hour=hour, minute=minute, second=second, tzinfo=tz
        )
        return int(dt_local.timestamp())
    except Exception as e:
        logger.exception("Failed to parse schedule date/time: %s", e)
        return None

def _build_attributes(fields):
    """
    Put business attributes (string-only) here.
    """
    attrs = {}
    # Examples based on your body
    acct = _field_value(fields, "Account_Number", "Account Number")
    if acct is not None:
        attrs["Account_Number"] = str(acct)

    meter = _field_value(fields, "Meter_Number", "Meter Number")
    if meter is not None:
        attrs["Meter_Number"] = str(meter)

    customer_type = _field_value(fields, "Customer_Type", "Customer Type")
    if customer_type:
        attrs["Customer_Type"] = str(customer_type)

    service_type = _field_value(fields, "Service_Type", "Service Type")
    if service_type:
        attrs["Service_Type"] = str(service_type)

    return attrs

def _build_references(body, fields, scheduled_epoch):
    """
    Convert misc fields to References with correct Type.
    Allowed types: STRING | NUMBER | EMAIL | URL | DATE
    """
    refs = {}

    # From fields
    email = _field_value(fields, "Sample_Email", "Sample Email")
    if email:
        refs["Sample_Email"] = {"Value": str(email), "Type": "EMAIL"}

    # Booleans -> STRING "true"/"false"
    self_assign = _field_value(fields, "selfAssign", "Self Assign")
    if self_assign is not None:
        refs["Self_Assign"] = {"Value": str(bool(self_assign)).lower(), "Type": "STRING"}

    # Optional: surface checkbox as STRING
    sample_checkbox = _field_value(fields, "Sample_Checkbox", "Sample Checkbox")
    if sample_checkbox is not None:
        refs["Sample_Checkbox"] = {"Value": str(bool(sample_checkbox)).lower(), "Type": "STRING"}

    # Optional: include the scheduled time also as a DATE-type reference for visibility
    '''
    if scheduled_epoch is not None:
        refs["Scheduled_For"] = {"Value": str(scheduled_epoch), "Type": "DATE"}
    '''

    # Helpful trace refs from the top-level request (STRINGs)
    if body.get("agentName"):
        refs["Agent_Name"] = {"Value": body["agentName"], "Type": "STRING"}
    if body.get("agentRoutingProfile"):
        refs["Agent_Routing_Profile"] = {"Value": body["agentRoutingProfile"], "Type": "STRING"}
    if body.get("agentARN"):
        refs["Agent_ARN"] = {"Value": body["agentARN"], "Type": "STRING"}
    if body.get("agentRoutingProfileARN"):
        refs["RoutingProfile_ARN"] = {"Value": body["agentRoutingProfileARN"], "Type": "STRING"}

    return refs

def handle_post_task_template_app(body):
    try:
        logger.info("Incoming body: %s", body)

        fields = body.get("fields", [])
        if not isinstance(fields, list):
            fields = []

        # Task Name (explicitly requested): prefer name 'taskName' or label 'Task Name', else fall back to 'T'
        task_name = _field_value(fields, "taskName", "Task Name", "T")
        if not task_name:
            task_name = "Task"  # minimal fallback

        # Description
        description = _field_value(fields, "description", "Description") or ""

        # ScheduledTime (epoch seconds)
        scheduled_epoch = _build_scheduled_time(fields)

        attributes = _build_attributes(fields)
        references = _build_references(body, fields, scheduled_epoch)

        start_kwargs = {
            "InstanceId": INSTANCE_ID,
            "Name": task_name,                 # <-- Name should be taskName (from your form)
            "Description": description,
            "Attributes": attributes,
            "References": references,
            "ContactFlowId": "5be486e1-bf19-4094-a5b7-e3da975bdd61"
        }

        # Use Quick Connect for routing (recommended)
        '''
        if QUICK_CONNECT_ID:
            start_kwargs["QuickConnectId"] = QUICK_CONNECT_ID
        '''

        # Only include ScheduledTime if provided
        '''
        if scheduled_epoch is not None:
            # Boto3 accepts int epoch; you can also pass a datetime
            start_kwargs["ScheduledTime"] = scheduled_epoch
        '''

        logger.info("start_task_contact kwargs (redacted where needed): %s", {**start_kwargs, "References": f"{len(references)} refs"})

        resp = connect.start_task_contact(**start_kwargs)
        logger.info("start_task_contact response: %s", resp)

        return _resp(200, {
            "message": "Task created.",
            "contactId": resp.get("ContactId"),
            "taskArn": resp.get("ContactArn"),
            "scheduledTime": scheduled_epoch
        })

    except Exception as e:
        logger.exception("Error creating task")
        return _resp(500, {"error": str(e)})
