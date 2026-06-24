#!/usr/bin/env python3
"""Portable CLI for the Akiflow private API skill.

All output is JSON. Credentials are read from environment or the active
Hermes profile .env via akiflow_client.client.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from akiflow_client import AkiflowAPI  # noqa: E402


def emit(value: Any, compact: bool = False) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":") if compact else None, indent=None if compact else 2, sort_keys=True))


def add_common_filters(p: argparse.ArgumentParser, *, dates: bool = True, limit: bool = True) -> None:
    if dates:
        p.add_argument("--date-from")
        p.add_argument("--date-to")
    if limit:
        p.add_argument("--limit", type=int)


def require_confirm(args: argparse.Namespace) -> None:
    if not getattr(args, "confirm", False):
        raise SystemExit("Refusing write: pass --confirm after explicit user approval.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Akiflow private API CLI for agent skills")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="check local configuration without making API calls")
    sub.add_parser("capabilities", help="show API capability map")

    p = sub.add_parser("tasks", help="list tasks")
    p.add_argument("--done", choices=["true", "false", "all"], default="false")
    p.add_argument("--status", type=int)
    p.add_argument("--list-id")
    p.add_argument("--priority", type=int)
    add_common_filters(p)

    sub.add_parser("projects", help="list projects/labels")
    sub.add_parser("tags", help="list tags")

    p = sub.add_parser("events", help="list calendar events")
    p.add_argument("--calendar-id")
    add_common_filters(p)

    sub.add_parser("calendars", help="list calendars")

    p = sub.add_parser("time-slots", help="list Akiflow time slots")
    add_common_filters(p)

    p = sub.add_parser("recordings", help="list Meeting Assistant recordings")
    add_common_filters(p)

    p = sub.add_parser("recording", help="get one recording")
    p.add_argument("recording_id")

    p = sub.add_parser("meeting-briefs", help="list pre-meeting briefs")
    add_common_filters(p)

    p = sub.add_parser("meeting-brief", help="get one meeting brief")
    p.add_argument("brief_id")

    p = sub.add_parser("create-task", help="create an Akiflow task")
    p.add_argument("--title", required=True)
    p.add_argument("--description")
    p.add_argument("--date")
    p.add_argument("--datetime")
    p.add_argument("--due-date")
    p.add_argument("--duration", type=int, default=0, help="minutes")
    p.add_argument("--priority", type=int)
    p.add_argument("--list-id", dest="listId")
    p.add_argument("--confirm", action="store_true")

    p = sub.add_parser("edit-task", help="edit selected task fields")
    p.add_argument("task_id")
    for name in ["title", "description", "date", "datetime", "due-date"]:
        p.add_argument(f"--{name}")
    p.add_argument("--duration", type=int)
    p.add_argument("--priority", type=int)
    p.add_argument("--status", type=int)
    p.add_argument("--list-id", dest="listId")
    p.add_argument("--confirm", action="store_true")

    p = sub.add_parser("mark-done", help="mark a task done")
    p.add_argument("task_id")
    p.add_argument("--confirm", action="store_true")

    p = sub.add_parser("schedule-task", help="schedule/plan a task")
    p.add_argument("task_id")
    p.add_argument("--date", required=True)
    p.add_argument("--datetime")
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--confirm", action="store_true")

    p = sub.add_parser("unschedule-task", help="remove schedule from a task")
    p.add_argument("task_id")
    p.add_argument("--keep-planned", action="store_true", help="do not move back to Inbox")
    p.add_argument("--confirm", action="store_true")

    p = sub.add_parser("create-task-from-action-item", help="turn a Meeting Assistant action item into a task")
    p.add_argument("recording_id")
    p.add_argument("action_item_id")
    p.add_argument("--confirm", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "status":
        emit({"configured": AkiflowAPI.configured(), "auth": "AKIFLOW_REFRESH_TOKEN or AKIFLOW_ACCESS_TOKEN"}, args.compact)
        return 0
    if args.command == "capabilities":
        emit(AkiflowAPI.capabilities(), args.compact)
        return 0

    cmd = args.command
    if cmd in {"create-task", "edit-task", "mark-done", "schedule-task", "unschedule-task", "create-task-from-action-item"}:
        require_confirm(args)

    api = AkiflowAPI()
    if cmd == "tasks":
        done = None if args.done == "all" else args.done == "true"
        data = api.list_tasks(done=done, status=args.status, date_from=args.date_from, date_to=args.date_to, list_id=args.list_id, priority=args.priority, limit=args.limit)
    elif cmd == "projects":
        data = api.list_projects()
    elif cmd == "tags":
        data = api.list_tags()
    elif cmd == "events":
        data = api.list_events(calendar_id=args.calendar_id, date_from=args.date_from, date_to=args.date_to, limit=args.limit)
    elif cmd == "calendars":
        data = api.list_calendars()
    elif cmd == "time-slots":
        data = api.list_time_slots(date_from=args.date_from, date_to=args.date_to, limit=args.limit)
    elif cmd == "recordings":
        data = api.list_recordings(date_from=args.date_from, date_to=args.date_to, limit=args.limit)
    elif cmd == "recording":
        data = api.get_recording(args.recording_id)
    elif cmd == "meeting-briefs":
        data = api.list_meeting_briefs(date_from=args.date_from, date_to=args.date_to, limit=args.limit)
    elif cmd == "meeting-brief":
        data = api.get_meeting_brief(args.brief_id)
    elif cmd == "create-task":
        require_confirm(args)
        data = api.create_task(title=args.title, description=args.description, date=args.date, datetime=args.datetime, due_date=args.due_date, duration=args.duration, priority=args.priority, listId=args.listId)
    elif cmd == "edit-task":
        require_confirm(args)
        fields = {"title": args.title, "description": args.description, "date": args.date, "datetime": args.datetime, "due_date": args.due_date, "duration": args.duration, "priority": args.priority, "status": args.status, "listId": args.listId}
        data = api.update_task(args.task_id, **{k: v for k, v in fields.items() if v is not None})
    elif cmd == "mark-done":
        require_confirm(args)
        data = api.mark_task_done(args.task_id)
    elif cmd == "schedule-task":
        require_confirm(args)
        data = api.schedule_task(args.task_id, date=args.date, datetime_value=args.datetime, duration=args.duration)
    elif cmd == "unschedule-task":
        require_confirm(args)
        data = api.unschedule_task(args.task_id, to_inbox=not args.keep_planned)
    elif cmd == "create-task-from-action-item":
        require_confirm(args)
        data = api.create_task_from_action_item(args.recording_id, args.action_item_id)
    else:
        parser.error(f"unknown command {cmd}")
    emit(data, args.compact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
