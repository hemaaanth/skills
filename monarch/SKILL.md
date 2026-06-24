---
name: monarch
description: Monarch Money personal finance API. Use for account balances, transactions, budgets, cashflow, recurring expenses, net worth, categories, tags, holdings, account history, and explicitly confirmed Monarch updates. Triggers on "my finances", "bank accounts", "spending", "budget", "transactions", "net worth", "cashflow", "Monarch" or "Monarch Money".
---

# Monarch Money

Personal finance management through the unofficial Monarch Money API.

The portable interface is `scripts/monarch.py`. Any agent that can read files and run shell commands can use this skill. Native agent integrations should live under `adapters/<agent>/` and call the same `monarch_client` package instead of duplicating API logic.

## Setup

Install dependencies in a virtual environment:

```bash
cd skills/monarch
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Authenticate with Monarch's current web login flow:

```bash
python scripts/monarch.py login --email you@example.com --interactive
```

If Monarch asks for an email one-time code, rerun with the code or stay in `--interactive` and paste it when prompted:

```bash
python scripts/monarch.py login --email you@example.com --interactive --email-otp 123456
```

The current web app authenticates GraphQL with session cookies plus CSRF/browser client headers, not always with a visible `Authorization` header. The CLI stores web-cookie auth in:

- `~/.monarchmoney/web_session.json` — non-secret metadata such as device UUID/client version
- `~/.monarchmoney/cookies.txt` — secret session cookies

Both are written with restrictive permissions where supported. Do not print or paste cookies, tokens, passwords, or OTP codes into logs.

Legacy browser/API tokens can still be saved if available:

```bash
python scripts/monarch.py set-token "Token YOUR_TOKEN_HERE"
```

Legacy tokens are saved to `~/.monarchmoney/session.json`.

## Read-only commands

```bash
# Auth/session check
python scripts/monarch.py status

# Account balances and account metadata
python scripts/monarch.py accounts
python scripts/monarch.py account-types
python scripts/monarch.py account-history ACCOUNT_ID
python scripts/monarch.py account-holdings ACCOUNT_ID
python scripts/monarch.py recent-balances --start 2026-01-01
python scripts/monarch.py snapshots-by-type --start 2026-01-01 --timeframe month
python scripts/monarch.py aggregate-snapshots --start 2026-01-01 --end 2026-01-31
python scripts/monarch.py institutions
python scripts/monarch.py subscription

# Transactions
python scripts/monarch.py transactions --limit 50
python scripts/monarch.py transactions --search "Amazon"
python scripts/monarch.py transactions --start 2026-01-01 --end 2026-01-31
python scripts/monarch.py transaction-summary
python scripts/monarch.py transaction-details TRANSACTION_ID
python scripts/monarch.py transaction-splits TRANSACTION_ID
python scripts/monarch.py categories
python scripts/monarch.py category-groups
python scripts/monarch.py transaction-tags

# Planning/reporting
python scripts/monarch.py budgets --start 2026-01-01
python scripts/monarch.py cashflow --start 2026-01-01 --end 2026-01-31
python scripts/monarch.py cashflow-summary --start 2026-01-01 --end 2026-01-31
python scripts/monarch.py recurring
python scripts/monarch.py networth
```

All commands output JSON. Add `--compact` before the subcommand for compact JSON:

```bash
python scripts/monarch.py --compact accounts
```

Some normalized commands support `--raw` after the subcommand to return the upstream response:

```bash
python scripts/monarch.py transactions --raw --limit 10
```

## Confirmed side-effecting commands

Never run these unless the user explicitly asks. Every side-effecting command requires `--confirm`.

`refresh` asks Monarch to sync connected institution data. It does not directly edit transactions/budgets/accounts, but it can pull new balances or transactions into Monarch:

```bash
python scripts/monarch.py refresh --confirm
python scripts/monarch.py refresh --confirm --wait
```

Higher-risk writes also require `MONARCH_ALLOW_WRITE=1`:

```bash
export MONARCH_ALLOW_WRITE=1
python scripts/monarch.py create-transaction --date 2026-01-01 --account-id ACCOUNT_ID --amount 12.34 --merchant "Coffee" --category-id CATEGORY_ID --confirm
python scripts/monarch.py update-transaction TRANSACTION_ID --notes "Updated note" --confirm
python scripts/monarch.py delete-transaction TRANSACTION_ID --confirm
python scripts/monarch.py set-transaction-tags TRANSACTION_ID --tag-ids TAG_ID_1,TAG_ID_2 --confirm
python scripts/monarch.py update-transaction-splits TRANSACTION_ID --split-data '[{"amount":5}]' --confirm
python scripts/monarch.py create-category --group-id GROUP_ID --name "New Category" --confirm
python scripts/monarch.py delete-category CATEGORY_ID --confirm
python scripts/monarch.py create-tag --name "Tax" --color "#3366ff" --confirm
python scripts/monarch.py set-budget-amount --category-id CATEGORY_ID --amount 500 --start 2026-01-01 --confirm
python scripts/monarch.py create-manual-account --account-type asset --account-subtype cash --name "Cash" --balance 100 --confirm
python scripts/monarch.py update-account ACCOUNT_ID --name "New Name" --confirm
python scripts/monarch.py delete-account ACCOUNT_ID --confirm
python scripts/monarch.py upload-balance-history ACCOUNT_ID balances.csv --confirm
```

## Common queries

**Total cash/depository balance:**

```bash
python scripts/monarch.py accounts | jq '[.[] | select(.type == "depository") | .currentBalance] | add'
```

**This month's spending by category:**

```bash
python scripts/monarch.py cashflow | jq '.byCategory'
```

**Largest recent transactions:**

```bash
python scripts/monarch.py transactions --limit 100 | jq 'sort_by(-.amount) | .[0:10]'
```

## Adapters

The skill is portable without adapters. Optional native integrations can live in `adapters/<agent>/`.

A Hermes example adapter is included at `adapters/hermes/`. It exposes read tools plus confirmed account refresh and uses the same `monarch_client` package.

## Reconnect and account-health operations

This skill includes reusable operational scripts for connected-account repair and monitoring. Keep these in the skill repo so every compatible agent can use the same behavior instead of relying on profile-local copies.

```bash
# Generate an on-demand MX/Finicity reconnect URL for a broken credential.
python scripts/generate_monarch_reconnect_link.py "Institution name"
python scripts/generate_monarch_reconnect_link.py --credential-id CREDENTIAL_UUID

# Quiet no-agent/watchdog account-health check; prints only when action is needed.
HERMES_HOME=/path/to/hermes-profile python scripts/monarch_account_health_watch.py
```

The watcher groups accounts by `credential.id`, stays silent when healthy, and avoids generating short-lived reconnect URLs during scheduled runs. See `references/monarch-reconnect-and-health-watch.md` before changing reconnect/cron behavior.

## Recovery / missing-data investigation notes

Monarch exposes more recovery primitives in its private GraphQL/web bundle than the portable CLI currently wraps:

- `forceRefreshAccount(input: {accountId, source})` / `forceRefreshAllAccounts(input: {source})` request a provider sync. `forceRefreshAllAccounts` returns a `forceRefreshOperationId`; poll `forceRefreshOperation(id)` for per-account `newTransactionCount`, `updatedTransactionCount`, `errorMessage`, and `errorDetail`. The older upstream `monarchmoney` package still uses deprecated `forceRefreshAccounts(accountIds)` and only checks `hasSyncInProgress`.
- `createMxCredentials` is documented in Monarch's schema as: "create credentials, perform the initial sync, and call extend history." This is evidence that MX supports an internal historical extension during initial connection, but no standalone user-facing `extendHistory`/`backfill` mutation has been found.
- `syncCredentialAfterReconnect(input: {credentialId})` clears `updateRequired` after repair/reconnect and triggers account sync to detect account changes.
- `resetAndSyncAccount(accountId)` appears in the web employee/debug menu as "Reset & Sync Account" and starts a sync after resetting the account. Treat it as dangerous/internal: do not run without explicit user confirmation and a fresh backup/export.
- `deleteSyncedTransactions(beforeDate, expectedAffectedTransactionsCount)` and `deleteSyncedSnapshots(beforeDate, expectedAffectedSnapshotsCount)` are destructive cleanup/reset primitives, not recovery. Do not use them for missing-data recovery unless intentionally rebuilding history from exports.
- `transferAccountDataAsync` can move transactions/snapshots between accounts and is useful for duplicate/reconnected-account repair, not for fetching missing upstream transactions.

When investigating missing transactions, group by `credential.id` / institution / data provider, not just visible account name. One upstream connection can back multiple accounts, so a Wealthsimple/MX gap can affect Chequing, credit card, USD cash, and investment/cash accounts together.

## Troubleshooting

- If help fails because dependencies are missing, that is a bug; `--help` should work without `monarchmoney` installed.
- If API calls fail with auth errors, rerun `login --interactive` or `set-token`.
- Monarch's API is unofficial/private and can change without notice.
