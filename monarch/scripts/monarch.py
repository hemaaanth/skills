#!/usr/bin/env python3
"""Portable CLI for the Monarch Money skill."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monarch_client.client import MonarchClient
from monarch_client.errors import ConfirmationRequiredError, MonarchClientError, WriteNotEnabledError
from monarch_client.formatters import (
    format_accounts,
    format_cashflow,
    format_categories,
    format_error,
    format_networth,
    format_ok,
    format_recurring,
    format_tags,
    format_transactions,
)
from monarch_client.session import save_token, session_file, web_session_file

HIGH_RISK_COMMANDS = {
    "create-transaction",
    "update-transaction",
    "delete-transaction",
    "set-transaction-tags",
    "update-transaction-splits",
    "create-category",
    "delete-category",
    "create-tag",
    "set-budget-amount",
    "create-manual-account",
    "update-account",
    "delete-account",
    "upload-balance-history",
}


def emit(data: Any, *, compact: bool = False) -> None:
    print(json.dumps(data, default=str, separators=(",", ":") if compact else None, indent=None if compact else 2))


def require_confirm(args: argparse.Namespace) -> None:
    if not getattr(args, "confirm", False):
        raise ConfirmationRequiredError("This command is side-effecting. Rerun with --confirm after checking the arguments.")


def require_write_enabled(args: argparse.Namespace) -> None:
    if getattr(args, "command", None) in HIGH_RISK_COMMANDS and os.getenv("MONARCH_ALLOW_WRITE") != "1":
        raise WriteNotEnabledError("Set MONARCH_ALLOW_WRITE=1 and pass --confirm to run high-risk mutating commands.")


def add_common_read_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", dest="start_date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", dest="end_date", help="End date (YYYY-MM-DD)")


def add_confirm(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--confirm", action="store_true", help="Required for side-effecting commands")


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_json_arg(value: str) -> Any:
    return json.loads(value)


async def handle_login(args: argparse.Namespace) -> Any:
    password = args.password
    if args.password_stdin:
        password = sys.stdin.read().rstrip("\n")
    if args.interactive or not password:
        password = getpass.getpass("Monarch password: ")
    mfa_code = args.mfa_code
    email_otp = args.email_otp
    client = MonarchClient()
    try:
        await client.login(args.email, password, mfa_code=mfa_code, mfa_secret_key=args.mfa_secret_key, email_otp=email_otp)
    except MonarchClientError as exc:
        if exc.error_type == "mfa_required" and args.interactive:
            prompt = "Email OTP or MFA code: "
            code = input(prompt).strip()
            await client.login(args.email, password, email_otp=code, mfa_code=mfa_code, mfa_secret_key=args.mfa_secret_key)
        else:
            raise
    return format_ok("Login succeeded; web session saved", session_file=str(web_session_file()))


async def handle_set_token(args: argparse.Namespace) -> Any:
    if args.no_verify:
        save_token(args.token)
        return format_ok("Token saved without verification", session_file=str(session_file()))
    result = await MonarchClient().set_token(args.token, verify=True)
    return format_ok("Token saved and verified", account_count=result.get("account_count"), session_file=str(session_file()))


async def dispatch_read(args: argparse.Namespace) -> Any:
    client = MonarchClient()
    cmd = args.command
    if cmd == "status":
        return await client.status()
    if cmd == "accounts":
        data = await client.get_accounts()
        return data if args.raw else format_accounts(data, include_hidden=args.all)
    if cmd == "account-types":
        return await client.get_account_type_options()
    if cmd == "recent-balances":
        return await client.get_recent_account_balances(start_date=args.start_date)
    if cmd == "snapshots-by-type":
        return await client.get_account_snapshots_by_type(start_date=args.start_date, timeframe=args.timeframe)
    if cmd == "aggregate-snapshots":
        return await client.get_aggregate_snapshots(start_date=args.start_date, end_date=args.end_date, account_type=args.account_type)
    if cmd == "account-holdings":
        return await client.get_account_holdings(args.account_id)
    if cmd == "account-history":
        return await client.get_account_history(args.account_id)
    if cmd == "institutions":
        return await client.get_institutions()
    if cmd == "subscription":
        return await client.get_subscription_details()
    if cmd == "budgets":
        return await client.get_budgets(start_date=args.start_date, end_date=args.end_date)
    if cmd == "transaction-summary":
        return await client.get_transactions_summary()
    if cmd == "transactions":
        kwargs: dict[str, Any] = {
            "limit": args.limit,
            "offset": args.offset,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "search": args.search or "",
            "category_ids": parse_csv(args.category_ids),
            "account_ids": parse_csv(args.account_ids),
            "tag_ids": parse_csv(args.tag_ids),
            "has_attachments": args.has_attachments,
            "has_notes": args.has_notes,
            "hidden_from_reports": args.hidden_from_reports,
            "is_split": args.is_split,
            "is_recurring": args.is_recurring,
            "imported_from_mint": args.imported_from_mint,
            "synced_from_institution": args.synced_from_institution,
        }
        data = await client.get_transactions(**kwargs)
        return data if args.raw else format_transactions(data)
    if cmd == "transaction-details":
        return await client.get_transaction_details(args.transaction_id)
    if cmd == "transaction-splits":
        return await client.get_transaction_splits(args.transaction_id)
    if cmd == "categories":
        data = await client.get_transaction_categories()
        return data if args.raw else format_categories(data)
    if cmd == "category-groups":
        return await client.get_transaction_category_groups()
    if cmd == "transaction-tags":
        data = await client.get_transaction_tags()
        return data if args.raw else format_tags(data)
    if cmd == "cashflow":
        data = await client.get_cashflow(limit=args.limit, start_date=args.start_date, end_date=args.end_date)
        return data if args.raw else format_cashflow(data)
    if cmd == "cashflow-summary":
        return await client.get_cashflow_summary(limit=args.limit, start_date=args.start_date, end_date=args.end_date)
    if cmd == "recurring":
        data = await client.get_recurring_transactions(start_date=args.start_date, end_date=args.end_date)
        return data if args.raw else format_recurring(data)
    if cmd == "networth":
        data = await client.get_accounts()
        return data if args.raw else format_networth(data)
    raise ValueError(f"Unknown read command: {cmd}")


async def dispatch_write(args: argparse.Namespace) -> Any:
    require_confirm(args)
    require_write_enabled(args)
    client = MonarchClient()
    cmd = args.command
    if cmd == "refresh":
        account_ids = parse_csv(args.account_ids) or None
        complete = await client.refresh_accounts(account_ids=account_ids, wait=args.wait, timeout=args.timeout, delay=args.delay)
        return {"status": "complete" if args.wait and complete else "started", "complete": bool(complete)}
    if cmd == "create-transaction":
        return await client.create_transaction(date=args.date, account_id=args.account_id, amount=args.amount, merchant_name=args.merchant, category_id=args.category_id, notes=args.notes or "", update_balance=args.update_balance)
    if cmd == "update-transaction":
        fields = {k: v for k, v in vars(args).items() if k in {"category_id", "merchant_name", "goal_id", "amount", "date", "hide_from_reports", "needs_review", "notes"} and v is not None}
        return await client.update_transaction(args.transaction_id, **fields)
    if cmd == "delete-transaction":
        return await client.delete_transaction(args.transaction_id)
    if cmd == "set-transaction-tags":
        return await client.set_transaction_tags(args.transaction_id, parse_csv(args.tag_ids))
    if cmd == "update-transaction-splits":
        return await client.update_transaction_splits(args.transaction_id, parse_json_arg(args.split_data))
    if cmd == "create-category":
        return await client.create_category(group_id=args.group_id, transaction_category_name=args.name, icon=args.icon, rollover_enabled=args.rollover_enabled, rollover_type=args.rollover_type)
    if cmd == "delete-category":
        return await client.delete_category(args.category_id)
    if cmd == "create-tag":
        return await client.create_tag(args.name, args.color)
    if cmd == "set-budget-amount":
        return await client.set_budget_amount(amount=args.amount, category_id=args.category_id, category_group_id=args.category_group_id, timeframe=args.timeframe, start_date=args.start_date, apply_to_future=args.apply_to_future)
    if cmd == "create-manual-account":
        return await client.create_manual_account(account_type=args.account_type, account_sub_type=args.account_subtype, is_in_net_worth=args.in_net_worth, account_name=args.name, account_balance=args.balance)
    if cmd == "update-account":
        fields = {"account_name": args.name, "account_balance": args.balance, "account_type": args.account_type, "account_sub_type": args.account_subtype, "include_in_net_worth": args.include_in_net_worth, "hide_from_summary_list": args.hide_from_summary_list, "hide_transactions_from_reports": args.hide_transactions_from_reports}
        return await client.update_account(args.account_id, **{k: v for k, v in fields.items() if v is not None})
    if cmd == "delete-account":
        return await client.delete_account(args.account_id)
    if cmd == "upload-balance-history":
        csv_content = Path(args.csv_file).read_text()
        return await client.upload_balance_history(args.account_id, csv_content)
    raise ValueError(f"Unknown write command: {cmd}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monarch Money CLI")
    parser.add_argument("--compact", action="store_true", help="Emit compact JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", help="Login with email/password; supports MFA")
    p.add_argument("--email", required=True)
    p.add_argument("--password", help="Password (prefer --interactive or --password-stdin)")
    p.add_argument("--password-stdin", action="store_true", help="Read password from stdin")
    p.add_argument("--mfa-code", help="MFA code if required")
    p.add_argument("--email-otp", help="Email OTP code if required by Monarch web login")
    p.add_argument("--mfa-secret-key", help="TOTP secret key for generated MFA")
    p.add_argument("--interactive", action="store_true", help="Prompt for password and MFA code without echoing password")
    p.set_defaults(handler=handle_login)

    p = sub.add_parser("set-token", help="Set auth token copied from browser DevTools")
    p.add_argument("token")
    p.add_argument("--no-verify", action="store_true", help="Save token without calling Monarch")
    p.set_defaults(handler=handle_set_token)

    read_handlers = ["status", "accounts", "account-types", "recent-balances", "snapshots-by-type", "aggregate-snapshots", "account-holdings", "account-history", "institutions", "subscription", "budgets", "transaction-summary", "transactions", "transaction-details", "transaction-splits", "categories", "category-groups", "transaction-tags", "cashflow", "cashflow-summary", "recurring", "networth"]
    for name in read_handlers:
        p = sub.add_parser(name, help=f"Read Monarch {name.replace('-', ' ')}")
        p.add_argument("--raw", action="store_true", help="Return raw upstream response where normalization exists")
        p.set_defaults(handler=dispatch_read)
        if name == "accounts":
            p.add_argument("--all", action="store_true", help="Include hidden accounts")
        if name in {"recent-balances"}:
            p.add_argument("--start", dest="start_date")
        if name in {"snapshots-by-type"}:
            p.add_argument("--start", dest="start_date", required=True)
            p.add_argument("--timeframe", default="month")
        if name in {"aggregate-snapshots", "budgets", "cashflow", "cashflow-summary", "recurring"}:
            add_common_read_filters(p)
        if name in {"cashflow", "cashflow-summary"}:
            p.add_argument("--limit", type=int)
        if name in {"account-holdings", "account-history"}:
            p.add_argument("account_id")
        if name in {"transaction-details", "transaction-splits"}:
            p.add_argument("transaction_id")
        if name == "aggregate-snapshots":
            p.add_argument("--account-type")
        if name == "transactions":
            p.add_argument("--limit", type=int, default=25)
            p.add_argument("--offset", type=int, default=0)
            add_common_read_filters(p)
            p.add_argument("--search")
            p.add_argument("--category-ids")
            p.add_argument("--account-ids")
            p.add_argument("--tag-ids")
            for flag in ["has-attachments", "has-notes", "hidden-from-reports", "is-split", "is-recurring", "imported-from-mint", "synced-from-institution"]:
                p.add_argument(f"--{flag}", action=argparse.BooleanOptionalAction, default=None)

    p = sub.add_parser("refresh", help="Request account sync/refresh from linked institutions")
    p.add_argument("--account-ids", help="Comma-separated account IDs; default all accounts")
    p.add_argument("--wait", action="store_true", help="Poll until refresh completes")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--delay", type=int, default=10)
    add_confirm(p)
    p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("create-transaction", help="Create manual transaction")
    p.add_argument("--date", required=True)
    p.add_argument("--account-id", required=True)
    p.add_argument("--amount", type=float, required=True)
    p.add_argument("--merchant", required=True)
    p.add_argument("--category-id", required=True)
    p.add_argument("--notes")
    p.add_argument("--update-balance", action="store_true")
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("update-transaction", help="Update transaction fields")
    p.add_argument("transaction_id")
    p.add_argument("--category-id")
    p.add_argument("--merchant-name")
    p.add_argument("--goal-id")
    p.add_argument("--amount", type=float)
    p.add_argument("--date")
    p.add_argument("--hide-from-reports", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--needs-review", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--notes")
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    for name, arg in [("delete-transaction", "transaction_id"), ("delete-category", "category_id"), ("delete-account", "account_id")]:
        p = sub.add_parser(name, help=f"Delete {name.split('-', 1)[1]}")
        p.add_argument(arg)
        add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("set-transaction-tags", help="Set tags on transaction")
    p.add_argument("transaction_id"); p.add_argument("--tag-ids", required=True)
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("update-transaction-splits", help="Update transaction splits from JSON array")
    p.add_argument("transaction_id"); p.add_argument("--split-data", required=True)
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("create-category", help="Create transaction category")
    p.add_argument("--group-id", required=True); p.add_argument("--name", required=True); p.add_argument("--icon", default="❓"); p.add_argument("--rollover-enabled", action="store_true"); p.add_argument("--rollover-type", default="monthly")
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("create-tag", help="Create transaction tag")
    p.add_argument("--name", required=True); p.add_argument("--color", required=True)
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("set-budget-amount", help="Set budget amount")
    p.add_argument("--amount", type=float, required=True); p.add_argument("--category-id"); p.add_argument("--category-group-id"); p.add_argument("--timeframe", default="month"); p.add_argument("--start", dest="start_date"); p.add_argument("--apply-to-future", action="store_true")
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("create-manual-account", help="Create manual account")
    p.add_argument("--account-type", required=True); p.add_argument("--account-subtype", required=True); p.add_argument("--name", required=True); p.add_argument("--balance", type=float, default=0); p.add_argument("--in-net-worth", action=argparse.BooleanOptionalAction, default=True)
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("update-account", help="Update account metadata")
    p.add_argument("account_id"); p.add_argument("--name"); p.add_argument("--balance", type=float); p.add_argument("--account-type"); p.add_argument("--account-subtype"); p.add_argument("--include-in-net-worth", action=argparse.BooleanOptionalAction, default=None); p.add_argument("--hide-from-summary-list", action=argparse.BooleanOptionalAction, default=None); p.add_argument("--hide-transactions-from-reports", action=argparse.BooleanOptionalAction, default=None)
    add_confirm(p); p.set_defaults(handler=dispatch_write)

    p = sub.add_parser("upload-balance-history", help="Upload balance history CSV for an account")
    p.add_argument("account_id"); p.add_argument("csv_file")
    add_confirm(p); p.set_defaults(handler=dispatch_write)
    return parser


async def async_main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = await args.handler(args)
        emit(result, compact=args.compact)
        return 0
    except MonarchClientError as exc:
        emit(exc.to_dict(), compact=args.compact)
        return 2
    except Exception as exc:
        emit(format_error("unexpected_error", str(exc)), compact=args.compact)
        return 1


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
