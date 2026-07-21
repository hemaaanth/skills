#!/usr/bin/env python3
"""Optional Hermes toolset adapter for the portable Dokploy skill.

The adapter delegates every API call to the canonical shell wrapper, preserving
its HTTPS, ID, timeout, and --confirm safeguards.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

try:
    from tools.registry import registry
except Exception:  # pragma: no cover - permits py_compile outside Hermes
    registry = None

TOOLSET = "dokploy"


def _skill_dir() -> Path:
    default = Path(__file__).resolve().parents[2]
    return Path(os.environ.get("DOKPLOY_SKILL_DIR") or default).expanduser()


def _script() -> Path:
    return _skill_dir() / "scripts" / "deployment.sh"


def check_dokploy_requirements() -> bool:
    return bool(os.environ.get("DOKPLOY_URL") and os.environ.get("DOKPLOY_API_KEY") and _script().is_file())


def _run(*args: str) -> str:
    script = _script()
    if not script.is_file():
        return json.dumps({"success": False, "error": f"Dokploy helper not found: {script}"})
    try:
        result = subprocess.run([str(script), *args], capture_output=True, text=True, check=False, timeout=30)
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "Dokploy helper timed out"})
    payload: dict[str, Any] = {"success": result.returncode == 0}
    if result.stdout:
        try:
            payload["data"] = json.loads(result.stdout)
        except json.JSONDecodeError:
            payload["data"] = result.stdout.strip()
    if result.returncode != 0:
        payload["error"] = result.stderr.strip() or "Dokploy helper failed"
    return json.dumps(payload, ensure_ascii=False, default=str)


def _register(name: str, description: str, properties: dict[str, Any], required: list[str], handler: Callable[[dict[str, Any]], str]) -> None:
    if registry is None:
        return
    registry.register(
        name=name,
        toolset=TOOLSET,
        schema={"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}},
        handler=lambda args, **_: handler(args),
        check_fn=check_dokploy_requirements,
        requires_env=["DOKPLOY_URL and DOKPLOY_API_KEY"],
    )


_ID = {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,200}$"}
_TAIL = {"type": "integer", "minimum": 1, "maximum": 10000, "default": 100}
_TYPE = {"type": "string", "enum": ["application", "compose", "server", "schedule", "previewDeployment", "backup", "volumeBackup"]}

_register("dokploy_app_deployments", "List deployments for an exact Dokploy application ID.", {"application_id": _ID}, ["application_id"], lambda a: _run("app", a["application_id"]))
_register("dokploy_compose_deployments", "List deployments for an exact Dokploy Compose ID.", {"compose_id": _ID}, ["compose_id"], lambda a: _run("compose", a["compose_id"]))
_register("dokploy_server_deployments", "List deployments for an exact Dokploy server ID.", {"server_id": _ID}, ["server_id"], lambda a: _run("server", a["server_id"]))
_register("dokploy_all_deployments", "List centralized Dokploy deployments.", {}, [], lambda a: _run("all"))
_register("dokploy_deployment_queue", "List the Dokploy deployment queue.", {}, [], lambda a: _run("queue"))
_register("dokploy_deployments_by_type", "List deployments by exact resource ID and supported Dokploy resource type.", {"resource_id": _ID, "resource_type": _TYPE}, ["resource_id", "resource_type"], lambda a: _run("type", a["resource_id"], a["resource_type"]))
_register("dokploy_deployment_logs", "Read recent logs for an exact deployment ID.", {"deployment_id": _ID, "tail": _TAIL}, ["deployment_id"], lambda a: _run("logs", a["deployment_id"], str(a.get("tail", 100))))
_register("dokploy_kill_deployment", "Destructive: stop an exact active deployment process. Obtain explicit user confirmation immediately before calling.", {"deployment_id": _ID, "confirm": {"type": "boolean", "description": "Must be true after explicit user confirmation."}}, ["deployment_id", "confirm"], lambda a: _run("kill", a["deployment_id"], "--confirm") if a.get("confirm") else json.dumps({"success": False, "error": "Explicit confirmation required: pass confirm=true."}))
_register("dokploy_remove_deployment", "Destructive: remove an exact deployment record. Obtain explicit user confirmation immediately before calling.", {"deployment_id": _ID, "confirm": {"type": "boolean", "description": "Must be true after explicit user confirmation."}}, ["deployment_id", "confirm"], lambda a: _run("remove", a["deployment_id"], "--confirm") if a.get("confirm") else json.dumps({"success": False, "error": "Explicit confirmation required: pass confirm=true."}))
