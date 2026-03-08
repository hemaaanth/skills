#!/usr/bin/env python3
"""Monarch Money CLI wrapper."""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    from monarchmoney import MonarchMoney, RequireMFAException
    from monarchmoney.monarchmoney import MonarchMoneyEndpoints
    MonarchMoneyEndpoints.BASE_URL = "https://api.monarch.com"
except ImportError:
    print("Install: pip install monarchmoney 'gql[aiohttp]<4'", file=sys.stderr)
    sys.exit(1)


SESSION_FILE = Path.home() / ".monarchmoney" / "session.json"


def get_client() -> MonarchMoney:
    """Get authenticated Monarch Money client."""
    mm = MonarchMoney()
    if SESSION_FILE.exists():
        with open(SESSION_FILE) as f:
            data = json.load(f)
            token = data.get("token")
            if token:
                mm.set_token(token)
                mm._headers["Authorization"] = f"Token {token}"
    return mm


def save_session(token: str):
    """Save session token."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump({"token": token}, f)


async def set_token(args):
    """Set token from browser."""
    token = args.token.replace("Token ", "").strip()
    
    # Verify token works
    mm = MonarchMoney()
    mm.set_token(token)
    mm._headers["Authorization"] = f"Token {token}"
    
    try:
        data = await mm.get_accounts()
        accounts = data.get("accounts", [])
        save_session(token)
        print(json.dumps({
            "status": "ok",
            "message": f"Token saved. Found {len(accounts)} accounts."
        }))
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)


async def accounts(args):
    """Get all accounts with balances."""
    mm = get_client()
    data = await mm.get_accounts()
    
    accounts = []
    for acct in data.get("accounts", []):
        if args.all or not acct.get("isHidden"):
            accounts.append({
                "id": acct.get("id"),
                "name": acct.get("displayName"),
                "institution": acct.get("credential", {}).get("institution", {}).get("name") if acct.get("credential") else None,
                "type": acct.get("type", {}).get("name"),
                "subtype": acct.get("subtype", {}).get("name"),
                "currentBalance": acct.get("currentBalance"),
                "isHidden": acct.get("isHidden"),
                "isAsset": acct.get("isAsset"),
                "includeInNetWorth": acct.get("includeInNetWorth"),
            })
    
    print(json.dumps(accounts, indent=2, default=str))


async def transactions(args):
    """Get transactions with optional filters."""
    mm = get_client()
    
    kwargs = {"limit": args.limit}
    
    if args.start:
        kwargs["start_date"] = args.start
    if args.end:
        kwargs["end_date"] = args.end
    if args.search:
        kwargs["search"] = args.search
    
    data = await mm.get_transactions(**kwargs)
    
    txns = []
    for tx in data.get("allTransactions", {}).get("results", []):
        txns.append({
            "id": tx.get("id"),
            "date": tx.get("date"),
            "amount": tx.get("amount"),
            "merchant": tx.get("merchant", {}).get("name") if tx.get("merchant") else None,
            "category": tx.get("category", {}).get("name") if tx.get("category") else None,
            "account": tx.get("account", {}).get("displayName") if tx.get("account") else None,
            "notes": tx.get("notes"),
            "isPending": tx.get("isPending"),
        })
    
    print(json.dumps(txns, indent=2, default=str))


async def budgets(args):
    """Get current budgets."""
    mm = get_client()
    
    now = datetime.now()
    start = now.replace(day=1).strftime("%Y-%m-%d")
    
    data = await mm.get_budgets(start_date=start)
    
    budgets = []
    for budget in data.get("budgetData", {}).get("budgetItems", []):
        budget_amt = budget.get("budgetAmount", {}).get("amount") or 0
        actual_amt = budget.get("actualAmount", {}).get("amount") or 0
        budgets.append({
            "category": budget.get("category", {}).get("name"),
            "categoryGroup": budget.get("category", {}).get("group", {}).get("name"),
            "budgetAmount": budget_amt,
            "actualAmount": actual_amt,
            "remaining": budget_amt - actual_amt,
        })
    
    print(json.dumps(budgets, indent=2, default=str))


async def cashflow(args):
    """Get cashflow summary."""
    mm = get_client()
    
    now = datetime.now()
    start = args.start or now.replace(day=1).strftime("%Y-%m-%d")
    end = args.end or now.strftime("%Y-%m-%d")
    
    data = await mm.get_cashflow(start_date=start, end_date=end)
    
    result = {
        "summary": data.get("summary", []),
        "byCategory": data.get("byCategory", []),
        "byCategoryGroup": data.get("byCategoryGroup", []),
        "byMerchant": data.get("byMerchant", []),
    }
    
    print(json.dumps(result, indent=2, default=str))


async def networth(args):
    """Get net worth breakdown."""
    mm = get_client()
    data = await mm.get_accounts()
    
    assets = 0
    liabilities = 0
    by_type = {}
    
    for acct in data.get("accounts", []):
        if not acct.get("includeInNetWorth"):
            continue
        
        balance = acct.get("currentBalance", 0) or 0
        acct_type = acct.get("type", {}).get("name", "other")
        
        if acct.get("isAsset"):
            assets += balance
        else:
            liabilities += abs(balance)
        
        by_type[acct_type] = by_type.get(acct_type, 0) + balance
    
    print(json.dumps({
        "netWorth": assets - liabilities,
        "assets": assets,
        "liabilities": liabilities,
        "byType": by_type,
    }, indent=2, default=str))


async def recurring(args):
    """Get recurring transactions."""
    mm = get_client()
    data = await mm.get_recurring_transactions()
    
    recurring = []
    for item in data.get("recurringTransactionStreams", []):
        recurring.append({
            "id": item.get("id"),
            "merchant": item.get("merchant", {}).get("name") if item.get("merchant") else None,
            "category": item.get("category", {}).get("name") if item.get("category") else None,
            "amount": item.get("amount"),
            "frequency": item.get("frequency"),
            "isActive": item.get("isActive"),
            "account": item.get("account", {}).get("displayName") if item.get("account") else None,
        })
    
    print(json.dumps(recurring, indent=2, default=str))


async def refresh(args):
    """Refresh all accounts."""
    mm = get_client()
    
    if args.wait:
        await mm.request_accounts_refresh_and_wait()
        print(json.dumps({"status": "complete"}))
    else:
        await mm.request_accounts_refresh()
        print(json.dumps({"status": "started", "message": "Refresh initiated"}))


def main():
    parser = argparse.ArgumentParser(description="Monarch Money CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Set token
    token_parser = subparsers.add_parser("set-token", help="Set auth token from browser")
    token_parser.add_argument("token", help="Token from browser DevTools")
    
    # Accounts
    acct_parser = subparsers.add_parser("accounts", help="List all accounts")
    acct_parser.add_argument("--all", action="store_true", help="Include hidden accounts")
    
    # Transactions
    tx_parser = subparsers.add_parser("transactions", help="Get transactions")
    tx_parser.add_argument("--limit", type=int, default=25, help="Number of transactions")
    tx_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    tx_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    tx_parser.add_argument("--search", help="Search term")
    
    # Budgets
    subparsers.add_parser("budgets", help="Get current budgets")
    
    # Cashflow
    cf_parser = subparsers.add_parser("cashflow", help="Get cashflow summary")
    cf_parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    cf_parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    
    # Net worth
    subparsers.add_parser("networth", help="Get net worth")
    
    # Recurring
    subparsers.add_parser("recurring", help="Get recurring transactions")
    
    # Refresh
    ref_parser = subparsers.add_parser("refresh", help="Refresh accounts")
    ref_parser.add_argument("--wait", action="store_true", help="Wait for completion")
    
    args = parser.parse_args()
    
    commands = {
        "set-token": set_token,
        "accounts": accounts,
        "transactions": transactions,
        "budgets": budgets,
        "cashflow": cashflow,
        "networth": networth,
        "recurring": recurring,
        "refresh": refresh,
    }
    
    asyncio.run(commands[args.command](args))


if __name__ == "__main__":
    main()
