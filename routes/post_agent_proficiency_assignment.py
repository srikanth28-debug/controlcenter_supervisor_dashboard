from utils.aws_clients import ddb as DDB, connect as CONNECT, table
from utils.logger import get_logger
from utils.http import respond
import os
import re
import json
import decimal
from datetime import datetime, date
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Logging & AWS Clients
# ---------------------------------------------------------------------------
logger = get_logger(__name__)
dynamodb = DDB
connect = CONNECT

# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------
INSTANCE_ID = os.environ["CONNECT_INSTANCE_ID"]
REGION = os.environ.get("AWS_REGION", "us-east-1")          
TABLE_MAPPING = os.environ["DDB_TABLE_TECO_PROFICIENCY_PROFILE_AGENT_MAPPING_US_EAST_1_DEV"]
TABLE_PROFILES = os.environ["DDB_TABLE_TECO_PROFICIENCY_PROFILE_US_EAST_1_DEV"]

mapping_table = dynamodb.Table(TABLE_MAPPING)
profile_table = dynamodb.Table(TABLE_PROFILES)

# ---------------------------------------------------------------------------
# JSON Encoder
# ---------------------------------------------------------------------------
class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)


# ---------------------------------------------------------------------------
# Connect Helpers
# ---------------------------------------------------------------------------
def _get_user_id_by_login(username: str) -> str:
    logger.info(f"[LOOKUP] Searching Connect user for login={username}")
    paginator = connect.get_paginator("list_users")
    for page in paginator.paginate(InstanceId=INSTANCE_ID):
        for u in page.get("UserSummaryList", []):
            if u.get("Username") == username:
                logger.info(f"[LOOKUP] Found user_id={u['Id']} for login={username}")
                return u["Id"]
    raise ValueError(f"User '{username}' not found in Connect")


def build_hierarchy_path(group_id: str) -> str:
    """Build full hierarchy path for display in Agent Profiles table."""
    try:
        resp = connect.describe_user_hierarchy_group(
            InstanceId=INSTANCE_ID, HierarchyGroupId=group_id
        )
        grp = resp.get("HierarchyGroup", {}) or {}
        path = grp.get("HierarchyPath", {}) or {}

        parts = []
        for level in ("LevelOne", "LevelTwo", "LevelThree", "LevelFour", "LevelFive"):
            lvl = path.get(level)
            if isinstance(lvl, dict) and "Name" in lvl:
                parts.append((lvl["Name"] or "").strip())

        leaf = (grp.get("Name") or "").strip()
        if leaf and (not parts or parts[-1] != leaf):
            parts.append(leaf)

        return " / ".join([p for p in parts if p]) or "-"
    except Exception as e:
        logger.warning(f"[WARN] Could not build hierarchy for {group_id}: {e}")
        return "-"


# ---------------------------------------------------------------------------
# Proficiency Normalization Helpers
# ---------------------------------------------------------------------------
def _level_to_int(level):
    try:
        n = int(float(level))
        return n if 1 <= n <= 5 else None
    except Exception:
        return None


def _norm_items(items, require_level=True):
    """Normalize proficiencies from DynamoDB to Connect API format."""
    valid, invalid = [], []
    if not isinstance(items, list):
        return [], [{"item": items, "reason": "Must be a list"}]

    for it in items:
        if isinstance(it, str):
            m = re.match(r"^\s*([^=]+)=([^(]+?)(?:\s*\(L(\d+)\))?\s*$", it)
            if m:
                it = {
                    "attributeName": m.group(1).strip(),
                    "attributeValue": m.group(2).strip(),
                    "level": int(m.group(3)) if m.group(3) else 1
                }
            else:
                invalid.append({"item": it, "reason": "Unrecognized string format"})
                continue

        name = it.get("attributeName") or it.get("AttributeName")
        value = it.get("attributeValue") or it.get("AttributeValue")
        lvl = it.get("level") or it.get("Level")

        if not name or not value:
            invalid.append({"item": it, "reason": "Missing attributeName/value"})
            continue

        out = {"AttributeName": name.strip(), "AttributeValue": value.strip()}
        if require_level:
            out["Level"] = _level_to_int(lvl) or 1
        valid.append(out)
    return valid, invalid


def _pairs(items):
    """Strip Level & remove duplicates for disassociate calls."""
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
    """Fetch a single profile's proficiencies by primary key (profile_name)."""
    try:
        resp = profile_table.get_item(Key={"profile_name": profile_name})
        item = resp.get("Item")
        if not item:
            return []
        profs = item.get("proficiencies", [])
        normed, _ = _norm_items(profs, True)
        return _pairs(normed)
    except Exception as e:
        logger.error(f"[COLLECT ERROR] Failed to fetch proficiencies for {profile_name}: {e}")
        return []


# ---------------------------------------------------------------------------
# Connect API Safe Wrapper
# ---------------------------------------------------------------------------
def _call_with_catch(fn, **kwargs):
    try:
        logger.info(f"[CONNECT CALL] {fn.__name__} args={json.dumps(kwargs, default=str)}")
        fn(**kwargs)
        return {"ok": True}
    except ClientError as e:
        err = e.response.get("Error", {})
        code = err.get("Code")
        msg = err.get("Message", str(e))
        logger.warning(f"[CONNECT ERROR] {fn.__name__} failed [{code}] {msg}")
        return {"ok": False, "code": code, "message": msg}
    except Exception as e:
        logger.exception(f"[CONNECT EXCEPTION] {fn.__name__} failed")
        return {"ok": False, "code": "InternalServerError", "message": str(e)}


# ---------------------------------------------------------------------------
# Profile and Mapping Helpers
# ---------------------------------------------------------------------------
def _get_profile_proficiencies(profile_id: str, profile_name: str):
    if profile_name:
        r = profile_table.get_item(Key={"profile_name": profile_name})
        if r.get("Item"):
            return r["Item"].get("proficiencies", [])
    if profile_id:
        scan = profile_table.scan(FilterExpression=Attr("profile_id").eq(profile_id))
        items = scan.get("Items", [])
        if items:
            return items[0].get("proficiencies", [])
    return []


def get_profile_name_by_agent_login(agent_login: str):
    try:
        response = mapping_table.get_item(Key={"agent_login": agent_login})
        item = response.get("Item")
        return item.get("profile_name") if item else None
    except Exception as e:
        logger.error(f"[ERROR] Failed to fetch profile_name for {agent_login}: {e}")
        return None


# ---------------------------------------------------------------------------
# Apply Logic
# ---------------------------------------------------------------------------
def _apply_proficiencies(agent_login, profs, profile_name=None):
    logger.info(f"[APPLY] Processing proficiencies for {agent_login}")
    user_id = _get_user_id_by_login(agent_login)

    # Wipe existing proficiencies
    if profile_name:
        all_known_pairs = _collect_all_profile_pairs(profile_name)
        if all_known_pairs:
            _call_with_catch(
                connect.disassociate_user_proficiencies,
                InstanceId=INSTANCE_ID,
                UserId=user_id,
                UserProficiencies=all_known_pairs
            )

    valid, _ = _norm_items(profs, True)
    if valid:
        return _call_with_catch(
            connect.associate_user_proficiencies,
            InstanceId=INSTANCE_ID,
            UserId=user_id,
            UserProficiencies=valid
        )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Main Handler
# ---------------------------------------------------------------------------
def handle_agent_proficiency_assignment(body):

    action = body.get("action")
    logger.info(f"[ACTION] {action}")

    try:
        # ---------- LIST ----------
        if action == "list":
            agents = []
            mappings = mapping_table.scan().get("Items", [])
            map_by_login = {m["agent_login"]: m for m in mappings}

            paginator = connect.get_paginator("list_users")
            for page in paginator.paginate(InstanceId=INSTANCE_ID):
                for summary in page.get("UserSummaryList", []):
                    user_id = summary.get("Id")
                    username = summary.get("Username", "")
                    user_detail = connect.describe_user(InstanceId=INSTANCE_ID, UserId=user_id)["User"]
                    ident = user_detail.get("IdentityInfo", {}) or {}
                    full_name = f"{ident.get('FirstName','').strip()} {ident.get('LastName','').strip()}".strip() or username
                    gid = user_detail.get("HierarchyGroupId")
                    hierarchy = build_hierarchy_path(gid) if gid else "-"

                    mapping = map_by_login.get(username, {})
                    agents.append({
                        "agent_login": username,
                        "agent_name": full_name,
                        "agent_hierarchy": hierarchy,
                        "profile_name": mapping.get("profile_name", ""),
                        "profile_id": mapping.get("profile_id", ""),
                        "hierarchy_group_id": gid or ""
                    })

            return respond(200, {"agents": agents})

        # ---------- CREATE ----------
        elif action == "create":
            item = {
                "agent_login": body["agent_login"],
                "agent_name": body.get("agent_name", ""),
                "profile_id": body.get("profile_id", ""),
                "profile_name": body.get("profile_name", "")
            }
            mapping_table.put_item(Item=item)
            profs = _get_profile_proficiencies(item["profile_id"], item["profile_name"])
            _apply_proficiencies(item["agent_login"], profs)
            return respond(200, {"message": "Agent profile created"})

        # ---------- UPDATE ----------
        elif action == "update":
            agent_login = body["agent_login"]
            new_pid = body.get("profile_id", "")
            new_pn = body.get("profile_name", "")
            old_profile_name = get_profile_name_by_agent_login(agent_login)

            if not new_pid and not new_pn:
                _apply_proficiencies(agent_login, [], old_profile_name)
                mapping_table.delete_item(Key={"agent_login": agent_login})
                return respond(200, {"message": "Profile cleared and proficiencies removed"})

            mapping_table.update_item(
                Key={"agent_login": agent_login},
                UpdateExpression="SET agent_name=:n, profile_id=:pid, profile_name=:pn",
                ExpressionAttributeValues={
                    ":n": body.get("agent_name", ""),
                    ":pid": new_pid,
                    ":pn": new_pn,
                },
            )
            profs = _get_profile_proficiencies(new_pid, new_pn)
            _apply_proficiencies(agent_login, profs, old_profile_name)
            return respond(200, {"message": "Agent profile updated"})

        # ---------- APPLY ----------
        elif action == "apply":
            agent_login = body["agent_login"]
            mapping = mapping_table.get_item(Key={"agent_login": agent_login}).get("Item")
            if not mapping:
                return respond(404, {"error": f"No mapping found for {agent_login}"})
            profs = _get_profile_proficiencies(mapping.get("profile_id", ""), mapping.get("profile_name", ""))
            _apply_proficiencies(agent_login, profs)
            return respond(200, {"message": "Proficiencies applied to Connect"})

        # ---------- CLEAR ----------
        elif action == "clear":
            agent_login = body["agent_login"]
            _apply_proficiencies(agent_login, [])
            return respond(200, {"message": "Cleared proficiencies"})

        # ---------- DELETE ----------
        elif action == "delete":
            mapping_table.delete_item(Key={"agent_login": body["agent_login"]})
            return respond(200, {"message": "Agent profile deleted"})

        # ---------- BULK ASSIGN ----------
        elif action == "bulk_assign":
            group_id = body.get("hierarchy_group_id")
            profile_id = body.get("profile_id")
            profile_name = body.get("profile_name")

            if not group_id or not (profile_id or profile_name):
                return respond(400, {"error": "hierarchy_group_id and (profile_id or profile_name) required"})

            profs = _get_profile_proficiencies(profile_id or "", profile_name or "")
            if not profs:
                return respond(404, {"error": "No proficiencies found for profile"})

            updated = []
            paginator = connect.get_paginator("list_users")
            for page in paginator.paginate(InstanceId=INSTANCE_ID):
                for u in page.get("UserSummaryList", []):
                    username = u.get("Username")
                    user_detail = connect.describe_user(InstanceId=INSTANCE_ID, UserId=u["Id"])["User"]
                    if user_detail.get("HierarchyGroupId") == group_id:
                        prev_profile_name = get_profile_name_by_agent_login(username)
                        first = user_detail.get("IdentityInfo", {}).get("FirstName", "").strip()
                        last = user_detail.get("IdentityInfo", {}).get("LastName", "").strip()
                        mapping_table.put_item(Item={
                            "agent_login": username,
                            "agent_name": f"{first} {last}".strip(),
                            "profile_id": profile_id or "",
                            "profile_name": profile_name or ""
                        })
                        _apply_proficiencies(username, profs, prev_profile_name)
                        updated.append(username)

            return respond(200, {"message": f"Bulk assigned to {len(updated)} agents", "updated_agents": updated})

        # ---------- BULK CLEAR ----------
        elif action == "bulk_clear":
            group_id = body.get("hierarchy_group_id")
            if not group_id:
                return respond(400, {"error": "hierarchy_group_id required"})

            cleared = []
            paginator = connect.get_paginator("list_users")
            for page in paginator.paginate(InstanceId=INSTANCE_ID):
                for u in page.get("UserSummaryList", []):
                    username = u.get("Username")
                    user_detail = connect.describe_user(InstanceId=INSTANCE_ID, UserId=u["Id"])["User"]
                    if user_detail.get("HierarchyGroupId") == group_id:
                        _apply_proficiencies(username, [])
                        cleared.append(username)

            return respond(200, {"message": f"Cleared proficiencies for {len(cleared)} agents", "cleared_agents": cleared})

        # ---------- INVALID ----------
        else:
            return respond(400, {"error": f"Invalid action '{action}'"})

    except Exception as e:
        logger.exception("[ERROR] Unhandled exception in handle_agent_proficiency_assignment")
        return respond(500, {"error": "InternalServerError", "message": str(e)})
