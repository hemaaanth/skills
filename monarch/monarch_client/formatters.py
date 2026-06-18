"""Output formatters for the Monarch Money skill."""

from __future__ import annotations

from typing import Any


def nested(data: dict[str, Any] | None, *keys: str) -> Any:
    value: Any = data or {}
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def format_error(error_type: str, message: str) -> dict[str, str]:
    return {"status": "error", "type": error_type, "message": message}


def format_ok(message: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "ok", "message": message}
    result.update(extra)
    return result


def format_accounts(data: dict[str, Any], include_hidden: bool = False) -> list[dict[str, Any]]:
    accounts = []
    for acct in data.get("accounts", []):
        if not include_hidden and acct.get("isHidden"):
            continue
        accounts.append(
            {
                "id": acct.get("id"),
                "name": acct.get("displayName") or acct.get("name"),
                "institution": nested(acct, "credential", "institution", "name"),
                "type": nested(acct, "type", "name") or acct.get("type"),
                "subtype": nested(acct, "subtype", "name") or acct.get("subtype"),
                "currentBalance": acct.get("currentBalance"),
                "isHidden": acct.get("isHidden"),
                "isAsset": acct.get("isAsset"),
                "includeInNetWorth": acct.get("includeInNetWorth"),
            }
        )
    return accounts


def format_transactions(data: dict[str, Any]) -> list[dict[str, Any]]:
    txs = data.get("allTransactions", {}).get("results", [])
    return [
        {
            "id": tx.get("id"),
            "date": tx.get("date"),
            "amount": tx.get("amount"),
            "merchant": nested(tx, "merchant", "name"),
            "category": nested(tx, "category", "name"),
            "account": nested(tx, "account", "displayName"),
            "notes": tx.get("notes"),
            "isPending": tx.get("isPending"),
        }
        for tx in txs
    ]


def format_categories(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": cat.get("id"),
            "name": cat.get("name"),
            "group": nested(cat, "group", "name"),
            "isSystemCategory": cat.get("isSystemCategory"),
        }
        for cat in data.get("categories", data.get("transactionCategories", []))
    ]


def format_tags(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": tag.get("id"), "name": tag.get("name"), "color": tag.get("color")}
        for tag in data.get("transactionTags", data.get("tags", []))
    ]


def format_recurring(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "merchant": nested(item, "merchant", "name"),
            "category": nested(item, "category", "name"),
            "amount": item.get("amount"),
            "frequency": item.get("frequency"),
            "isActive": item.get("isActive"),
            "account": nested(item, "account", "displayName"),
        }
        for item in data.get("recurringTransactionStreams", [])
    ]


def format_cashflow(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": data.get("summary", []),
        "byCategory": data.get("byCategory", []),
        "byCategoryGroup": data.get("byCategoryGroup", []),
        "byMerchant": data.get("byMerchant", []),
    }


def format_networth(accounts_data: dict[str, Any]) -> dict[str, Any]:
    assets = 0.0
    liabilities = 0.0
    by_type: dict[str, float] = {}
    for acct in accounts_data.get("accounts", []):
        if not acct.get("includeInNetWorth"):
            continue
        balance = acct.get("currentBalance", 0) or 0
        acct_type = nested(acct, "type", "name") or "other"
        if acct.get("isAsset"):
            assets += balance
        else:
            liabilities += abs(balance)
        by_type[acct_type] = by_type.get(acct_type, 0) + balance
    return {"netWorth": assets - liabilities, "assets": assets, "liabilities": liabilities, "byType": by_type}
