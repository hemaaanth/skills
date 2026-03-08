---
name: monarch
description: Monarch Money personal finance API. Use for checking account balances, transactions, budgets, cashflow, recurring expenses, and net worth. Triggers on "my finances", "bank accounts", "spending", "budget", "transactions", "net worth", "cashflow", "Monarch" or "Monarch Money".
---

# Monarch Money

Personal finance management via the Monarch Money API.

## Setup

Get your auth token from the Monarch web app:

1. Go to [app.monarch.com](https://app.monarch.com) and log in
2. Open DevTools (F12) → Network tab
3. Click any request to `api.monarch.com`
4. Copy the `Authorization` header value (starts with "Token ")

Then set it:
```bash
python skills/monarch/scripts/monarch.py set-token "Token YOUR_TOKEN_HERE"
```

Session is saved to `~/.monarchmoney/session.json` for reuse.

## Quick Commands

```bash
# Account balances
python skills/monarch/scripts/monarch.py accounts

# Recent transactions (default 25)
python skills/monarch/scripts/monarch.py transactions --limit 50

# Search transactions
python skills/monarch/scripts/monarch.py transactions --search "Amazon"

# Transactions by date range
python skills/monarch/scripts/monarch.py transactions --start 2026-01-01 --end 2026-01-31

# Current budgets
python skills/monarch/scripts/monarch.py budgets

# Cashflow summary
python skills/monarch/scripts/monarch.py cashflow

# Net worth
python skills/monarch/scripts/monarch.py networth

# Recurring transactions
python skills/monarch/scripts/monarch.py recurring

# Refresh all accounts
python skills/monarch/scripts/monarch.py refresh
```

## Output

All commands output JSON for easy parsing. Use `jq` for formatting:
```bash
python skills/monarch/scripts/monarch.py accounts | jq '.[] | {name, balance, type}'
```

## Common Queries

**Total cash on hand:**
```bash
python skills/monarch/scripts/monarch.py accounts | jq '[.[] | select(.type.name == "depository") | .currentBalance] | add'
```

**This month's spending by category:**
```bash
python skills/monarch/scripts/monarch.py cashflow | jq '.byCategory'
```

**Largest recent transactions:**
```bash
python skills/monarch/scripts/monarch.py transactions --limit 100 | jq 'sort_by(-.amount) | .[0:10]'
```
