#!/usr/bin/env python3
"""Portable Akiflow private API client.

Reverse-engineered from https://github.com/shrimpwtf/akiflow-mcp and the
Akiflow web application. Uses the web refresh-token flow plus private
v5/v3/aki endpoints. This module intentionally contains no credentials.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()


def _read_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def _env(name: str) -> str:
    return os.environ.get(name) or _read_env_file(_hermes_home() / ".env").get(name, "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class AkiflowConfig:
    refresh_token: str = ""
    access_token: str = ""
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "AkiflowConfig":
        refresh_token = _env("AKIFLOW_REFRESH_TOKEN")
        access_token = _env("AKIFLOW_ACCESS_TOKEN")
        if not refresh_token and not access_token:
            raise RuntimeError(
                "AKIFLOW_REFRESH_TOKEN or AKIFLOW_ACCESS_TOKEN is not configured. Prefer "
                "AKIFLOW_REFRESH_TOKEN from web.akiflow.com DevTools Network refreshToken; "
                "AKIFLOW_ACCESS_TOKEN can be used for short-lived smoke tests."
            )
        timeout = int(_env("AKIFLOW_TIMEOUT") or "30")
        return cls(refresh_token=refresh_token, access_token=access_token, timeout=timeout)


class AkiflowAPI:
    TASKS_URL = "https://api.akiflow.com/v5/tasks"
    PROJECTS_URL = "https://api.akiflow.com/v5/labels"
    TAGS_URL = "https://api.akiflow.com/v5/tags"
    EVENTS_URL = "https://api.akiflow.com/v5/events"
    EVENTS_WRITE_URL = "https://api.akiflow.com/v3/events"
    CALENDARS_URL = "https://api.akiflow.com/v5/calendars"
    TIME_SLOTS_URL = "https://api.akiflow.com/v5/time_slots"
    AKI_API_URL = "https://aki.akiflow.com/api/v1"
    TOKEN_URL = "https://web.akiflow.com/oauth/refreshToken"

    STATUS = {1: "Inbox", 2: "Planned", 4: "Snoozed", 7: "Someday", 10: "Scheduled"}
    PRIORITY = {-1: "Goal", 1: "High", 2: "Medium", 3: "Low"}

    def __init__(self, config: Optional[AkiflowConfig] = None) -> None:
        self.config = config or AkiflowConfig.from_env()
        self._access_token: Optional[str] = None
        self._cache_path = _hermes_home() / "akiflow" / "cache.json"
        self._cache: Dict[str, Any] = self._load_cache()

    @classmethod
    def configured(cls) -> bool:
        return bool(_env("AKIFLOW_REFRESH_TOKEN") or _env("AKIFLOW_ACCESS_TOKEN"))

    def _headers(self) -> Dict[str, str]:
        if not self._access_token:
            self._access_token = self.config.access_token or self._refresh_access_token()
            if self._access_token.startswith("Bearer "):
                self._access_token = self._access_token.split(" ", 1)[1]
        return {
            "Akiflow-Platform": "mac",
            "Authorization": f"Bearer {self._access_token}",
            "Referer": "https://web.akiflow.com/app/stable/29a83ee24d87ff96/static/js/801.chunk.js",
            "Akiflow-Client-Id": "b4edaac3-5dc7-4b20-bf58-de51efc2bec4",
            "Akiflow-Version": "2.71.5",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _refresh_access_token(self) -> str:
        if not self.config.refresh_token:
            raise RuntimeError("AKIFLOW_ACCESS_TOKEN expired or was rejected, and no AKIFLOW_REFRESH_TOKEN is configured for refresh.")
        payload = {"client_id": "10", "refresh_token": self.config.refresh_token}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.TOKEN_URL,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                # Cloudflare may reject bare Python urllib clients with 403 / 1010.
                # Match the web app's browser-origin token refresh request closely enough
                # for server-side Hermes smoke tests and scheduled runs.
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                "Origin": "https://web.akiflow.com",
                "Referer": "https://web.akiflow.com/",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        token = body.get("access_token")
        if not token:
            raise RuntimeError(f"Akiflow refreshToken did not return access_token: {body}")
        return token

    def _request(self, method: str, url: str, data: Any = None, *, binary: bool = False) -> Any:
        body = None if data is None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                raw = resp.read()
                if binary:
                    return raw
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self._access_token = self._refresh_access_token()
                req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
                with urllib.request.urlopen(req, timeout=self.config.timeout) as resp:
                    raw = resp.read()
                    if binary:
                        return raw
                    return json.loads(raw.decode("utf-8")) if raw else None
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Akiflow API {method} {url} failed HTTP {exc.code}: {detail}") from exc

    def _load_cache(self) -> Dict[str, Any]:
        try:
            return json.loads(self._cache_path.read_text())
        except Exception:
            return {"v5": {}, "aki": {}}

    def _save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(self._cache, indent=2, sort_keys=True))

    def _merge_list(self, response: Any) -> List[Dict[str, Any]]:
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in ("data", "items"):
                if isinstance(response.get(key), list):
                    return response[key]
            if isinstance(response.get("id"), str):
                return [response]
        return []

    def _sync_v5(self, key: str, url: str, deleted_pred, extra: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        state = self._cache.setdefault("v5", {}).setdefault(key, {"itemsById": {}, "syncToken": None, "updatedAt": None})
        merged = dict(state.get("itemsById") or {})

        def run(sync_token: Optional[str]) -> Optional[str]:
            page_token = sync_token
            next_token = sync_token
            seen: set[str] = set()
            while True:
                params = {"limit": "2500", **(extra or {})}
                if page_token:
                    params["sync_token"] = page_token
                full = f"{url}?{urllib.parse.urlencode(params)}"
                response = self._request("GET", full) or {}
                for item in response.get("data") or []:
                    item_id = item.get("id")
                    if not item_id:
                        continue
                    if deleted_pred(item):
                        merged.pop(item_id, None)
                    else:
                        merged[item_id] = item
                next_token = response.get("sync_token") or next_token
                if not response.get("has_next_page") or not response.get("sync_token"):
                    break
                if response["sync_token"] in seen:
                    break
                seen.add(response["sync_token"])
                page_token = response["sync_token"]
            return next_token

        try:
            sync_token = run(state.get("syncToken"))
        except RuntimeError as exc:
            if state.get("syncToken") and "HTTP 400" in str(exc):
                merged = {}
                sync_token = run(None)
            else:
                raise
        state.update({"itemsById": merged, "syncToken": sync_token, "updatedAt": _now_iso()})
        self._save_cache()
        return list(merged.values())

    def _refresh_aki(self, key: str, path: str, deleted_pred, per_page: int = 100, max_age_seconds: int = 60) -> List[Dict[str, Any]]:
        state = self._cache.setdefault("aki", {}).setdefault(key, {"itemsById": {}, "updatedAt": None})
        updated = state.get("updatedAt")
        if updated:
            try:
                age = time.time() - datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
                if age < max_age_seconds:
                    return list((state.get("itemsById") or {}).values())
            except Exception:
                pass
        items_by_id: Dict[str, Dict[str, Any]] = {}
        cursor = None
        seen: set[str] = set()
        while True:
            params = {"per_page": str(per_page)}
            if cursor:
                params["cursor"] = cursor
            response = self._request("GET", f"{self.AKI_API_URL}/{path}?{urllib.parse.urlencode(params)}") or {}
            for item in response.get("data") or []:
                if not deleted_pred(item):
                    items_by_id[item["id"]] = item
            cursor = response.get("next_cursor")
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        state.update({"itemsById": items_by_id, "updatedAt": _now_iso()})
        self._save_cache()
        return list(items_by_id.values())

    def _merge_v5_items(self, key: str, items: List[Dict[str, Any]], deleted_pred) -> None:
        state = self._cache.setdefault("v5", {}).setdefault(key, {"itemsById": {}, "syncToken": None, "updatedAt": None})
        items_by_id = dict(state.get("itemsById") or {})
        for item in items:
            item_id = item.get("id")
            if not item_id:
                continue
            if deleted_pred(item):
                items_by_id.pop(item_id, None)
            else:
                items_by_id[item_id] = item
        state.update({"itemsById": items_by_id, "updatedAt": _now_iso()})
        self._save_cache()

    @classmethod
    def capabilities(cls) -> Dict[str, Any]:
        return {
            "auth": "AKIFLOW_REFRESH_TOKEN -> POST https://web.akiflow.com/oauth/refreshToken with client_id=10; Bearer access token for API calls",
            "v5_read_sync": ["tasks", "labels/projects", "tags", "events", "calendars", "time_slots"],
            "writes": {
                "tasks_exposed": "PATCH https://api.akiflow.com/v5/tasks with client-generated UUIDs/partial updates",
                "time_slot_links_exposed": "PATCH task.time_slot_id via https://api.akiflow.com/v5/tasks",
                "recording_action_item_to_task_exposed": "POST https://aki.akiflow.com/api/v1/recordings/createTaskFromActionItem/{recording}/{item}",
                "events_reverse_engineered_not_exposed": "POST https://api.akiflow.com/v3/events (requires full calendar identity payload; leave unexposed until live-tested)",
                "time_slot_create_update_reverse_engineered_not_exposed": "PATCH https://api.akiflow.com/v5/time_slots",
            },
            "meeting_assistant": ["GET /recordings", "GET /recordings/{id}", "POST /recordings/createTaskFromActionItem/{recording}/{item}", "GET /researches"],
            "status_codes": cls.STATUS,
            "priority_codes": cls.PRIORITY,
        }

    # Reads
    def list_tasks(self, done: Optional[bool] = False, status: Optional[int] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, list_id: Optional[str] = None, priority: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        tasks = [t for t in self._sync_v5("tasks", self.TASKS_URL, lambda t: bool(t.get("deleted_at") or t.get("trashed_at"))) if not t.get("deleted_at") and not t.get("trashed_at")]
        if done is not None:
            tasks = [t for t in tasks if bool(t.get("done")) == done]
        if status is not None:
            tasks = [t for t in tasks if t.get("status") == status]
        if date_from:
            tasks = [t for t in tasks if (t.get("date") or t.get("datetime") or t.get("due_date") or "")[:10] >= date_from]
        if date_to:
            tasks = [t for t in tasks if (t.get("date") or t.get("datetime") or t.get("due_date") or "")[:10] <= date_to and (t.get("date") or t.get("datetime") or t.get("due_date"))]
        if list_id:
            tasks = [t for t in tasks if t.get("listId") == list_id]
        if priority is not None:
            tasks = [t for t in tasks if t.get("priority") == priority]
        tasks.sort(key=lambda t: t.get("date") or t.get("datetime") or t.get("due_date") or "9999-12-31")
        return tasks[:limit] if limit else tasks

    def list_projects(self) -> List[Dict[str, Any]]:
        return [p for p in self._sync_v5("projects", self.PROJECTS_URL, lambda p: bool(p.get("deleted_at"))) if not p.get("deleted_at")]

    def list_tags(self) -> List[Dict[str, Any]]:
        return [t for t in self._sync_v5("tags", self.TAGS_URL, lambda t: bool(t.get("deleted_at"))) if not t.get("deleted_at")]

    def list_events(self, calendar_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        events = [e for e in self._sync_v5("events", self.EVENTS_URL, lambda e: bool(e.get("deleted_at"))) if not e.get("deleted_at")]
        if calendar_id:
            events = [e for e in events if e.get("calendar_id") == calendar_id]
        if date_from:
            events = [e for e in events if (e.get("start_datetime") or e.get("start_date") or "")[:10] >= date_from]
        if date_to:
            events = [e for e in events if (e.get("start_datetime") or e.get("start_date") or "")[:10] <= date_to and (e.get("start_datetime") or e.get("start_date"))]
        events.sort(key=lambda e: e.get("start_datetime") or e.get("start_date") or "9999-12-31")
        return events[:limit] if limit else events

    def list_calendars(self) -> List[Dict[str, Any]]:
        return self._sync_v5("calendars", self.CALENDARS_URL, lambda c: c.get("deleted_at") is not None, {"with_deleted": "false"})

    def list_time_slots(self, date_from: Optional[str] = None, date_to: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        slots = [s for s in self._sync_v5("timeSlots", self.TIME_SLOTS_URL, lambda s: bool(s.get("deleted_at"))) if not s.get("deleted_at")]
        if date_from:
            slots = [s for s in slots if (s.get("start_time") or "")[:10] >= date_from]
        if date_to:
            slots = [s for s in slots if (s.get("start_time") or "")[:10] <= date_to]
        slots.sort(key=lambda s: s.get("start_time") or "9999-12-31")
        return slots[:limit] if limit else slots

    def list_recordings(self, date_from: Optional[str] = None, date_to: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = [r for r in self._refresh_aki("recordings", "recordings", lambda r: bool(r.get("deletedAt") or r.get("trashedAt"))) if not r.get("trashedAt")]
        if date_from:
            rows = [r for r in rows if ((r.get("data") or {}).get("startTime") or r.get("createdAt") or "")[:10] >= date_from]
        if date_to:
            rows = [r for r in rows if ((r.get("data") or {}).get("startTime") or r.get("createdAt") or "")[:10] <= date_to]
        return rows[:limit] if limit else rows

    def get_recording(self, recording_id: str) -> Dict[str, Any]:
        response = self._request("GET", f"{self.AKI_API_URL}/recordings/{recording_id}") or {}
        return response.get("data", response)

    def list_meeting_briefs(self, date_from: Optional[str] = None, date_to: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        rows = self._refresh_aki("meetingBriefs", "researches", lambda b: bool(b.get("deletedAt")))
        if date_from:
            rows = [b for b in rows if (b.get("createdAt") or "")[:10] >= date_from]
        if date_to:
            rows = [b for b in rows if (b.get("createdAt") or "")[:10] <= date_to]
        return rows[:limit] if limit else rows

    def get_meeting_brief(self, brief_id: str) -> Dict[str, Any]:
        response = self._request("GET", f"{self.AKI_API_URL}/researches/{brief_id}") or {}
        return response.get("data", response)

    # Writes
    def create_task(self, **kwargs: Any) -> List[Dict[str, Any]]:
        title = kwargs.get("title")
        if not title:
            raise ValueError("title is required")
        now = _now_iso()
        sorting = int(time.time() * 1000)
        task = {
            "id": str(uuid.uuid4()), "status": int(kwargs.get("status") or 1), "title": title,
            "sorting": sorting, "sorting_label": sorting, "duration": int(kwargs.get("duration") or 0) * 60,
            "date": kwargs.get("date"), "datetime": kwargs.get("datetime"), "plan_unit": None, "plan_period": None,
            "tags_ids": kwargs.get("tags_ids"), "time_slot_id": None, "links": [], "done": False, "done_at": None,
            "datetime_tz": kwargs.get("datetime_tz") or "UTC", "data": {}, "original_date": None, "original_datetime": None,
            "recurring_id": None, "recurrence": None, "search_text": "", "due_date": kwargs.get("due_date"),
            "calendar_id": None, "recurrence_version": None, "content": None, "origin": None, "connector_id": None,
            "origin_id": None, "origin_account_id": None, "doc": None, "trashed_at": None,
            "global_created_at": now, "deleted_at": None, "global_updated_at": now,
            "global_list_id_updated_at": None, "global_tags_ids_updated_at": None,
        }
        if kwargs.get("description") is not None:
            task["description"] = kwargs["description"]
        if kwargs.get("priority") is not None:
            task["priority"] = int(kwargs["priority"])
        if kwargs.get("listId") is not None:
            task["listId"] = kwargs["listId"]
        if task["date"] or task["datetime"]:
            task["status"] = int(kwargs.get("status") or 2)
        result = self._merge_list(self._request("PATCH", self.TASKS_URL, [task]))
        self._merge_v5_items("tasks", result, lambda t: bool(t.get("deleted_at") or t.get("trashed_at")))
        return result

    def update_task(self, task_id: str, **fields: Any) -> List[Dict[str, Any]]:
        payload = {"id": task_id, "global_updated_at": _now_iso()}
        for key in ["title", "description", "date", "datetime", "due_date", "duration", "priority", "status", "done", "listId", "tags_ids", "time_slot_id"]:
            if key in fields:
                value = fields[key]
                if key == "duration" and value is not None:
                    value = int(value) * 60
                if key in {"priority", "status"} and value is not None:
                    value = int(value)
                payload[key] = value
        result = self._merge_list(self._request("PATCH", self.TASKS_URL, [payload]))
        self._merge_v5_items("tasks", result, lambda t: bool(t.get("deleted_at") or t.get("trashed_at")))
        return result

    def mark_task_done(self, task_id: str) -> List[Dict[str, Any]]:
        return self.update_task(task_id, done=True, done_at=_now_iso())

    def schedule_task(self, task_id: str, date: str, datetime_value: Optional[str] = None, duration: int = 30) -> List[Dict[str, Any]]:
        return self.update_task(task_id, date=date, datetime=datetime_value, duration=duration, status=2)

    def unschedule_task(self, task_id: str, to_inbox: bool = True) -> List[Dict[str, Any]]:
        fields: Dict[str, Any] = {"date": None, "datetime": None}
        if to_inbox:
            fields["status"] = 1
        return self.update_task(task_id, **fields)

    def create_task_from_action_item(self, recording_id: str, action_item_id: str) -> Any:
        return self._request("POST", f"{self.AKI_API_URL}/recordings/createTaskFromActionItem/{recording_id}/{action_item_id}")
