# Updated post_agent_proficiency_assignment.py with clear-profile support and env-var tables
import os, re, json, logging, decimal
from datetime import datetime, date
import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "us-east-1")
INSTANCE_ID = os.environ.get("CONNECT_INSTANCE_ID", "5ad694d7-d5f2-434d-9c35-e6369cbd77e7")

DDB = boto3.resource("dynamodb", region_name=REGION)
TABLE_MAPPING  = DDB.Table(os.environ.get("DDB_TABLE_MAPPING","teco-proficiency-profile-agent-mapping-us-east-1-dev"))
TABLE_PROFILES = DDB.Table(os.environ.get("DDB_TABLE_PROFILES","teco-proficiency-profile-us-east-1-dev"))

CONNECT = boto3.client("connect", region_name=REGION)

def _cors_headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
        "Access-Control-Allow-Headers":"Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
    }

def _response(status, payload):
    return {"statusCode": status, "headers": _cors_headers(), "body": json.dumps(payload, default=str)}

def _get_user_id_by_login(username: str) -> str:
    paginator = CONNECT.get_paginator("list_users")
    for page in paginator.paginate(InstanceId=INSTANCE_ID):
        for u in page.get("UserSummaryList", []):
            if u.get("Username") == username:
                return u["Id"]
    raise ValueError(f"User '{username}' not found in Connect")

def build_hierarchy_path(group_id: str) -> str:
    try:
        resp = CONNECT.describe_user_hierarchy_group(InstanceId=INSTANCE_ID, HierarchyGroupId=group_id)
        grp  = resp.get("HierarchyGroup", {}) or {}
        path = grp.get("HierarchyPath", {}) or {}
        parts = []
        for key in ("LevelOne","LevelTwo","LevelThree","LevelFour","LevelFive"):
            lvl = path.get(key)
            if isinstance(lvl, dict) and "Name" in lvl:
                parts.append((lvl["Name"] or "").strip())
        leaf = (grp.get("Name") or "").strip()
        if leaf and (not parts or parts[-1] != leaf):
            parts.append(leaf)
        return " / ".join([p for p in parts if p]) or "-"
    except Exception as e:
        logger.warning(f"[WARN] Could not build hierarchy for {group_id}: {e}")
        return "-"

def _level_to_int(level):
    try:
        n = int(float(level))
        return n if 1 <= n <= 5 else None
    except Exception:
        return None

def _norm_items(items, require_level=True):
    valid, invalid = [], []
    if not isinstance(items, list):
        return [], [{"item": items, "reason": "Must be a list"}]
    for it in items:
        if isinstance(it, str):
            m = re.match(r"^\s*([^=]+)=([^(]+?)(?:\s*\(L(\d+)\))?\s*$", it)
            if m:
                it = {"attributeName": m.group(1).strip(), "attributeValue": m.group(2).strip(), "level": int(m.group(3)) if m.group(3) else 1}
            else:
                invalid.append({"item": it, "reason": "Unrecognized string format"})
                continue
        name  = (it or {}).get("attributeName") or it.get("AttributeName")
        value = (it or {}).get("attributeValue") or it.get("AttributeValue")
        lvl   = (it or {}).get("level") or it.get("Level")
        if not name or not value:
            invalid.append({"item": it, "reason": "Missing attributeName/value"})
            continue
        out = {"AttributeName": name.strip(), "AttributeValue": value.strip()}
        if require_level:
            out["Level"] = _level_to_int(lvl) or 1
        valid.append(out)
    return valid, invalid

def _pairs(items):
    seen, out = set(), []
    for p in items or []:
        an = p.get("AttributeName") or p.get("attributeName")
        av = p.get("AttributeValue") or p.get("attributeValue")
        if not an or not av:
            continue
        key = f"{an}::{av}"
        if key in seen: 
            continue
        seen.add(key)
        out.append({"AttributeName": an, "AttributeValue": av})
    return out

def _collect_all_profile_pairs(profile_name: str):
    all_pairs = []
    try:
        resp = TABLE_PROFILES.get_item(Key={"profile_name": profile_name})
        item = resp.get("Item")
        if not item:
            return []
        profs = item.get("proficiencies", [])
        normed, _ = _norm_items(profs, True)
        for p in normed:
            all_pairs.append({"AttributeName": p["AttributeName"], "AttributeValue": p["AttributeValue"]})
        return _pairs(all_pairs)
    except Exception as e:
        logger.error(f"[COLLECT ERROR] Failed to fetch proficiencies for {profile_name}: {e}")
        return []

def _call_with_catch(fn, **kwargs):
    try:
        fn(**kwargs); return {"ok": True}
    except ClientError as e:
        err  = e.response.get("Error", {})
        return {"ok": False, "code": err.get("Code"), "message": err.get("Message")}
    except Exception as e:
        return {"ok": False, "code": "InternalServerError", "message": str(e)}

def _get_profile_proficiencies(profile_id: str, profile_name: str):
    if profile_name:
        r = TABLE_PROFILES.get_item(Key={"profile_name": profile_name})
        if r.get("Item"):
            return r["Item"].get("proficiencies", [])
    if profile_id:
        scan = TABLE_PROFILES.scan(FilterExpression=Attr("profile_id").eq(profile_id))
        items = scan.get("Items", [])
        if items:
            return items[0].get("proficiencies", [])
    return []

def get_profile_name_by_agent_login(agent_login: str) -> str:
    try:
        response = TABLE_MAPPING.get_item(Key={"agent_login": agent_login})
        item = response.get("Item")
        if not item:
            return None
        return item.get("profile_name")
    except Exception as e:
        logger.error(f"[ERROR] Failed to fetch profile_name for {agent_login}: {e}")
        return None

def _apply_proficiencies(agent_login, profs, profile_name = None):
    user_id = _get_user_id_by_login(agent_login)
    if profile_name:
        all_known_pairs = _collect_all_profile_pairs(profile_name)
        if all_known_pairs:
            _call_with_catch(CONNECT.disassociate_user_proficiencies, InstanceId=INSTANCE_ID, UserId=user_id, UserProficiencies=all_known_pairs)
    valid, invalid = _norm_items(profs, True)
    if valid:
        return _call_with_catch(CONNECT.associate_user_proficiencies, InstanceId=INSTANCE_ID, UserId=user_id, UserProficiencies=valid)
    return {"ok": True}

def handle_agent_proficiency_assignment(body):
    action = body.get("action")
    if action == "list":
        agents = []
        mappings = TABLE_MAPPING.scan().get("Items", [])
        map_by_login = {m["agent_login"]: m for m in mappings}
        paginator = CONNECT.get_paginator("list_users")
        for page in paginator.paginate(InstanceId=INSTANCE_ID):
            for summary in page.get("UserSummaryList", []):
                user_id  = summary.get("Id")
                username = summary.get("Username", "")
                u = CONNECT.describe_user(InstanceId=INSTANCE_ID, UserId=user_id)["User"]
                ident = u.get("IdentityInfo", {}) or {}
                full_name = f"{(ident.get('FirstName') or '').strip()} {(ident.get('LastName') or '').strip()}".strip() or username
                gid = u.get("HierarchyGroupId")
                hierarchy = build_hierarchy_path(gid) if gid else "-"
                m = map_by_login.get(username, {})
                agents.append({
                    "agent_login": username,
                    "agent_name":  full_name,
                    "agent_hierarchy": hierarchy,
                    "profile_name": m.get("profile_name", ""),
                    "profile_id":   m.get("profile_id", ""),
                    "hierarchy_group_id": gid or ""
                })
        return _response(200, {"agents": agents})

    elif action == "create":
        item = {
            "agent_login": body["agent_login"],
            "agent_name":  body.get("agent_name",""),
            "profile_id":  body.get("profile_id",""),
            "profile_name":body.get("profile_name",""),
        }
        TABLE_MAPPING.put_item(Item=item)
        profs = _get_profile_proficiencies(item["profile_id"], item["profile_name"])
        _apply_proficiencies(item["agent_login"], profs)
        return _response(200, {"message": "Agent profile created"})

    elif action == "update":
        agent_login = body["agent_login"]
        new_pid  = body.get("profile_id","")
        new_pn   = body.get("profile_name","")
        old_profile_name = get_profile_name_by_agent_login(agent_login)
        if not new_pid and not new_pn:
            _apply_proficiencies(agent_login, [], old_profile_name)
            TABLE_MAPPING.delete_item(Key={"agent_login": agent_login})
            return _response(200, {"message": "Profile cleared and proficiencies removed"})
        TABLE_MAPPING.update_item(
            Key={"agent_login": agent_login},
            UpdateExpression="SET agent_name=:n, profile_id=:pid, profile_name=:pn",
            ExpressionAttributeValues={":n": body.get("agent_name",""), ":pid": new_pid, ":pn": new_pn},
        )
        profs = _get_profile_proficiencies(new_pid, new_pn)
        _apply_proficiencies(agent_login, profs, old_profile_name)
        return _response(200, {"message": "Agent profile updated"})

    elif action == "apply":
        agent_login = body["agent_login"]
        m = TABLE_MAPPING.get_item(Key={"agent_login": agent_login}).get("Item")
        if not m:
            return _response(404, {"error": f"No mapping found for {agent_login}"})
        profs = _get_profile_proficiencies(m.get("profile_id",""), m.get("profile_name",""))
        _apply_proficiencies(agent_login, profs)
        return _response(200, {"message": "Proficiencies applied to Connect"})

    elif action == "clear":
        agent_login = body["agent_login"]
        _apply_proficiencies(agent_login, [])
        return _response(200, {"message": "Cleared proficiencies"})

    elif action == "delete":
        TABLE_MAPPING.delete_item(Key={"agent_login": body["agent_login"]})
        return _response(200, {"message": "Agent profile deleted"})

    elif action == "bulk_assign":
        group_id = body.get("hierarchy_group_id")
        profile_id = body.get("profile_id")
        profile_name = body.get("profile_name")
        if not group_id or not (profile_id or profile_name):
            return _response(400, {"error": "hierarchy_group_id and (profile_id or profile_name) required"})
        profs = _get_profile_proficiencies(profile_id or "", profile_name or "")
        if not profs:
            return _response(404, {"error": "No proficiencies found for profile"})
        updated = []
        paginator = CONNECT.get_paginator("list_users")
        for page in paginator.paginate(InstanceId=INSTANCE_ID):
            for u in page.get("UserSummaryList", []):
                username = u.get("Username")
                prev_profile_name = get_profile_name_by_agent_login(username)
                full_user = CONNECT.describe_user(InstanceId=INSTANCE_ID, UserId=u["Id"])["User"]
                if full_user.get("HierarchyGroupId") == group_id:
                    first = (full_user.get("IdentityInfo",{}).get("FirstName","") or "").strip()
                    last  = (full_user.get("IdentityInfo",{}).get("LastName","") or "").strip()
                    TABLE_MAPPING.put_item(Item={
                        "agent_login": username,
                        "agent_name": f"{first} {last}".strip(),
                        "profile_id": profile_id or "",
                        "profile_name": profile_name or ""
                    })
                    _apply_proficiencies(username, profs, prev_profile_name)
                    updated.append(username)
        return _response(200, {"message": f"Bulk assigned to {len(updated)} agents", "updated_agents": updated})

    elif action == "bulk_clear":
        group_id = body.get("hierarchy_group_id")
        if not group_id:
            return _response(400, {"error": "hierarchy_group_id required"})
        cleared = []
        paginator = CONNECT.get_paginator("list_users")
        for page in paginator.paginate(InstanceId=INSTANCE_ID):
            for u in page.get("UserSummaryList", []):
                username = u.get("Username")
                full_user = CONNECT.describe_user(InstanceId=INSTANCE_ID, UserId=u["Id"])["User"]
                if full_user.get("HierarchyGroupId") == group_id:
                    _apply_proficiencies(username, [])
                    cleared.append(username)
        return _response(200, {"message": f"Cleared proficiencies for {len(cleared)} agents", "cleared_agents": cleared})

    else:
        return _response(400, {"error": "Invalid action"})
