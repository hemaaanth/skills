"""Optional Hermes toolset adapter for the portable Monarch skill.

Copy this file into a Hermes Agent `tools/` directory and register the tool
names in a `monarch` toolset. It intentionally exposes read tools plus a
confirmed account refresh only; broader writes should be added locally after
explicit approval.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

# When this file is copied into Hermes, point MONARCH_SKILL_DIR at the skill
# directory if `monarch_client` is not otherwise importable.
import os

_default_skill_dir = Path(__file__).resolve().parents[2]
_skill_dir = os.getenv("MONARCH_SKILL_DIR") or (str(_default_skill_dir) if (_default_skill_dir / "monarch_client").exists() else None)
if _skill_dir and _skill_dir not in sys.path:
    sys.path.insert(0, _skill_dir)

try:
    from tools.registry import registry
except Exception:  # pragma: no cover - allows py_compile outside Hermes
    registry = None

from monarch_client.client import MonarchClient
from monarch_client.errors import MonarchClientError
from monarch_client.formatters import format_accounts, format_cashflow, format_error, format_networth, format_recurring, format_transactions


def _run(coro):
    try:
        return json.dumps(asyncio.run(coro), default=str)
    except MonarchClientError as exc:
        return json.dumps(exc.to_dict())
    except Exception as exc:
        return json.dumps(format_error("unexpected_error", str(exc)))


async def _status() -> dict[str, Any]:
    return await MonarchClient().status()


async def _accounts(include_hidden: bool = False) -> list[dict[str, Any]]:
    data = await MonarchClient().get_accounts()
    return format_accounts(data, include_hidden=include_hidden)


async def _transactions(limit: int = 25, start_date: str | None = None, end_date: str | None = None, search: str = "") -> list[dict[str, Any]]:
    data = await MonarchClient().get_transactions(limit=limit, start_date=start_date, end_date=end_date, search=search)
    return format_transactions(data)


async def _budgets(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    return await MonarchClient().get_budgets(start_date=start_date, end_date=end_date)


async def _cashflow(start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    return format_cashflow(await MonarchClient().get_cashflow(start_date=start_date, end_date=end_date))


async def _recurring(start_date: str | None = None, end_date: str | None = None) -> list[dict[str, Any]]:
    return format_recurring(await MonarchClient().get_recurring_transactions(start_date=start_date, end_date=end_date))


async def _networth() -> dict[str, Any]:
    return format_networth(await MonarchClient().get_accounts())


async def _refresh(confirm: bool = False, wait: bool = False) -> dict[str, Any]:
    if not confirm:
        return {"status": "error", "type": "confirmation_required", "message": "Refresh syncs connected institutions. Pass confirm=true to run."}
    complete = await MonarchClient().refresh_accounts(wait=wait)
    return {"status": "complete" if wait and complete else "started", "complete": bool(complete)}


def check_requirements() -> bool:
    try:
        from monarch_client.session import has_auth
        return bool(has_auth())
    except Exception:
        return False


def _register(name: str, description: str, properties: dict[str, Any], required: list[str], handler):
    if registry is None:
        return
    registry.register(
        name=name,
        toolset="monarch",
        schema={
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
        handler=lambda args, **kw: handler(args),
        check_fn=check_requirements,
    )


_register("monarch_status", "Check Monarch authentication and account count.", {}, [], lambda args: _run(_status()))
_register("monarch_accounts", "List Monarch accounts and balances.", {"include_hidden": {"type": "boolean", "default": False}}, [], lambda args: _run(_accounts(args.get("include_hidden", False))))
_register("monarch_transactions", "List Monarch transactions with optional filters.", {"limit": {"type": "integer", "default": 25}, "start_date": {"type": "string"}, "end_date": {"type": "string"}, "search": {"type": "string"}}, [], lambda args: _run(_transactions(args.get("limit", 25), args.get("start_date"), args.get("end_date"), args.get("search", ""))))
_register("monarch_budgets", "Get Monarch budget data.", {"start_date": {"type": "string"}, "end_date": {"type": "string"}}, [], lambda args: _run(_budgets(args.get("start_date"), args.get("end_date"))))
_register("monarch_cashflow", "Get Monarch cashflow data.", {"start_date": {"type": "string"}, "end_date": {"type": "string"}}, [], lambda args: _run(_cashflow(args.get("start_date"), args.get("end_date"))))
_register("monarch_recurring", "Get recurring Monarch transactions.", {"start_date": {"type": "string"}, "end_date": {"type": "string"}}, [], lambda args: _run(_recurring(args.get("start_date"), args.get("end_date"))))
_register("monarch_networth", "Calculate net worth from Monarch accounts.", {}, [], lambda args: _run(_networth()))
_register("monarch_refresh_accounts", "Side-effecting: ask Monarch to refresh/sync connected account data. Requires confirm=true.", {"confirm": {"type": "boolean"}, "wait": {"type": "boolean", "default": False}}, ["confirm"], lambda args: _run(_refresh(args.get("confirm", False), args.get("wait", False))))
