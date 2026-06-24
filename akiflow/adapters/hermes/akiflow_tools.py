#!/usr/bin/env python3
"""Optional Hermes toolset adapter for the portable Akiflow skill.

Install by symlinking/copying this file into a Hermes Agent `tools/` directory
and registering the `akiflow` toolset. This adapter contains no business logic;
it imports the canonical `akiflow_client` package from the portable skill repo.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from tools.registry import registry
except Exception:  # pragma: no cover - allows py_compile outside Hermes
    registry = None

TOOLSET = "akiflow"


def _skill_dir() -> Path:
    default = Path(__file__).resolve().parents[2]
    return Path(os.environ.get("AKIFLOW_SKILL_DIR") or default).expanduser()


def _ensure_skill_importable() -> None:
    root = str(_skill_dir())
    if root not in sys.path:
        sys.path.insert(0, root)


def _api_class():
    _ensure_skill_importable()
    from akiflow_client import AkiflowAPI
    return AkiflowAPI


def _api():
    return _api_class()()


def check_akiflow_requirements() -> bool:
    try:
        return bool(_api_class().configured())
    except Exception:
        return False


def _json_result(fn: Callable[[], Any]) -> str:
    try:
        return json.dumps({"success": True, "data": fn()}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)


def _int(args: Dict[str, Any], name: str, default: Optional[int] = None) -> Optional[int]:
    value = args.get(name, default)
    if value in (None, ""):
        return default
    return int(value)


def _bool(args: Dict[str, Any], name: str, default: Optional[bool] = None) -> Optional[bool]:
    value = args.get(name, default)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _list(args: Dict[str, Any], name: str) -> Optional[List[str]]:
    value = args.get(name)
    if value in (None, "", []):
        return None
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return [str(x).strip() for x in value if str(x).strip()]


def _required(args: Dict[str, Any], name: str) -> str:
    value = args.get(name)
    if value in (None, ""):
        raise ValueError(f"{name} is required")
    return str(value)


# Handlers
def akiflow_capabilities(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api_class().capabilities())


def akiflow_list_tasks(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_tasks(
        done=_bool(args, "done", False), status=_int(args, "status"),
        date_from=args.get("date_from"), date_to=args.get("date_to"),
        list_id=args.get("listId"), priority=_int(args, "priority"), limit=_int(args, "limit"),
    ))


def akiflow_create_task(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().create_task(
        title=args.get("title"), description=args.get("description"), date=args.get("date"),
        datetime=args.get("datetime"), due_date=args.get("due_date"), duration=_int(args, "duration", 0),
        priority=_int(args, "priority"), status=_int(args, "status"), listId=args.get("listId"),
        tags_ids=_list(args, "tags_ids"),
    ))


def akiflow_edit_task(args: Dict[str, Any], **_: Any) -> str:
    fields = {k: args[k] for k in ["title", "description", "date", "datetime", "due_date", "duration", "priority", "status", "done", "listId", "tags_ids"] if k in args}
    return _json_result(lambda: _api().update_task(_required(args, "id"), **fields))


def akiflow_mark_task_done(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().mark_task_done(_required(args, "id")))


def akiflow_schedule_task(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().schedule_task(_required(args, "id"), _required(args, "date"), args.get("datetime"), _int(args, "duration", 30) or 30))


def akiflow_unschedule_task(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().unschedule_task(_required(args, "id"), _bool(args, "to_inbox", True) is not False))


def akiflow_list_projects(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_projects())


def akiflow_list_tags(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_tags())


def akiflow_list_events(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_events(args.get("calendar_id"), args.get("date_from"), args.get("date_to"), _int(args, "limit")))


def akiflow_list_calendars(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_calendars())


def akiflow_list_time_slots(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_time_slots(args.get("date_from"), args.get("date_to"), _int(args, "limit")))


def akiflow_add_task_to_time_slot(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().update_task(_required(args, "task_id"), time_slot_id=_required(args, "time_slot_id")))


def akiflow_remove_task_from_time_slot(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().update_task(_required(args, "task_id"), time_slot_id=None))


def akiflow_list_recordings(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_recordings(args.get("date_from"), args.get("date_to"), _int(args, "limit")))


def akiflow_get_recording(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().get_recording(_required(args, "id")))


def akiflow_list_meeting_briefs(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().list_meeting_briefs(args.get("date_from"), args.get("date_to"), _int(args, "limit")))


def akiflow_get_meeting_brief(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().get_meeting_brief(_required(args, "id")))


def akiflow_create_task_from_action_item(args: Dict[str, Any], **_: Any) -> str:
    return _json_result(lambda: _api().create_task_from_action_item(_required(args, "recording_id"), _required(args, "action_item_id")))


def _schema(properties: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


def _register(name: str, description: str, properties: Dict[str, Any], required: Optional[List[str]], handler: Callable[..., str]) -> None:
    if registry is None:
        return
    registry.register(name=name, toolset=TOOLSET, schema={"name": name, "description": description, "parameters": _schema(properties, required)}, handler=handler, check_fn=check_akiflow_requirements, requires_env=["AKIFLOW_REFRESH_TOKEN or AKIFLOW_ACCESS_TOKEN"])


_STR = {"type": "string"}
_DATE = {"type": "string", "description": "YYYY-MM-DD"}
_DT = {"type": "string", "description": "ISO 8601 datetime"}
_LIMIT = {"type": "integer", "minimum": 1, "maximum": 500, "description": "Maximum records to return"}
_STATUS = {"type": "integer", "enum": [1, 2, 4, 7, 10], "description": "1=Inbox, 2=Planned, 4=Snoozed, 7=Someday, 10=Scheduled"}
_PRIORITY = {"type": "integer", "enum": [-1, 1, 2, 3], "description": "-1=Goal, 1=High, 2=Medium, 3=Low"}

if registry is not None:
    registry.register(
        name="akiflow_capabilities",
        toolset=TOOLSET,
        schema={"name": "akiflow_capabilities", "description": "Show Akiflow private API endpoints, auth model, status/priority codes, and Hermes exposure.", "parameters": _schema({})},
        handler=akiflow_capabilities,
        check_fn=check_akiflow_requirements,
        requires_env=["AKIFLOW_REFRESH_TOKEN or AKIFLOW_ACCESS_TOKEN"],
    )
_register("akiflow_list_tasks", "List Akiflow tasks with filters. Defaults to incomplete active tasks sorted by task date/due date.", {"done": {"type": "boolean"}, "status": _STATUS, "date_from": _DATE, "date_to": _DATE, "listId": {"type": "string", "description": "Project/label UUID"}, "priority": _PRIORITY, "limit": _LIMIT}, None, akiflow_list_tasks)
_register("akiflow_create_task", "Create a new Akiflow task. Duration is minutes; date/datetime auto-plans the task.", {"title": _STR, "description": _STR, "date": _DATE, "datetime": _DT, "due_date": _DATE, "duration": {"type": "integer", "minimum": 0}, "priority": _PRIORITY, "status": _STATUS, "listId": _STR, "tags_ids": {"type": "array", "items": {"type": "string"}}}, ["title"], akiflow_create_task)
_register("akiflow_edit_task", "Edit an existing Akiflow task. Pass null to clear nullable fields.", {"id": _STR, "title": _STR, "description": {"type": ["string", "null"]}, "date": {"type": ["string", "null"]}, "datetime": {"type": ["string", "null"]}, "due_date": {"type": ["string", "null"]}, "duration": {"type": ["integer", "null"]}, "priority": {"type": ["integer", "null"], "enum": [-1, 1, 2, 3, None]}, "status": _STATUS, "done": {"type": "boolean"}, "listId": {"type": ["string", "null"]}, "tags_ids": {"type": ["array", "null"], "items": {"type": "string"}}}, ["id"], akiflow_edit_task)
_register("akiflow_mark_task_done", "Mark an Akiflow task complete.", {"id": _STR}, ["id"], akiflow_mark_task_done)
_register("akiflow_schedule_task", "Schedule/plan a task for a date and optional datetime. Duration is minutes.", {"id": _STR, "date": _DATE, "datetime": _DT, "duration": {"type": "integer", "minimum": 1}}, ["id", "date"], akiflow_schedule_task)
_register("akiflow_unschedule_task", "Remove task date/datetime and optionally move it back to inbox.", {"id": _STR, "to_inbox": {"type": "boolean", "default": True}}, ["id"], akiflow_unschedule_task)
_register("akiflow_list_projects", "List Akiflow projects/labels and folders. Folders have type='folder'.", {}, None, akiflow_list_projects)
_register("akiflow_list_tags", "List Akiflow tags.", {}, None, akiflow_list_tags)
_register("akiflow_list_events", "List calendar events from Akiflow v5 API with optional calendar/date filters.", {"calendar_id": _STR, "date_from": _DATE, "date_to": _DATE, "limit": _LIMIT}, None, akiflow_list_events)
_register("akiflow_list_calendars", "List connected Akiflow calendars including read_only and primary metadata.", {}, None, akiflow_list_calendars)
_register("akiflow_list_time_slots", "List internal Akiflow time slots/blocks with optional date filters.", {"date_from": _DATE, "date_to": _DATE, "limit": _LIMIT}, None, akiflow_list_time_slots)
_register("akiflow_add_task_to_time_slot", "Attach a task to an existing Akiflow time slot block.", {"task_id": _STR, "time_slot_id": _STR}, ["task_id", "time_slot_id"], akiflow_add_task_to_time_slot)
_register("akiflow_remove_task_from_time_slot", "Detach a task from its Akiflow time slot block.", {"task_id": _STR}, ["task_id"], akiflow_remove_task_from_time_slot)
_register("akiflow_list_recordings", "List Akiflow Meeting Assistant recordings with summaries/action items/transcripts when available.", {"date_from": _DATE, "date_to": _DATE, "limit": _LIMIT}, None, akiflow_list_recordings)
_register("akiflow_get_recording", "Get full detail for one Meeting Assistant recording including transcript/action items.", {"id": _STR}, ["id"], akiflow_get_recording)
_register("akiflow_list_meeting_briefs", "List Akiflow pre-meeting research briefs.", {"date_from": _DATE, "date_to": _DATE, "limit": _LIMIT}, None, akiflow_list_meeting_briefs)
_register("akiflow_get_meeting_brief", "Get full detail for one Akiflow meeting brief/research record.", {"id": _STR}, ["id"], akiflow_get_meeting_brief)
_register("akiflow_create_task_from_action_item", "Create an Akiflow task from a Meeting Assistant recording action item.", {"recording_id": _STR, "action_item_id": _STR}, ["recording_id", "action_item_id"], akiflow_create_task_from_action_item)
