# Monarch reconnect and account-health watch patterns

Operational notes for Monarch Money account connector repair and monitoring.

## Reconnect / repair flows

Monarch's web app exposes reconnect flows that may not be wrapped by public clients:

| Provider | API path | Result |
|---|---|---|
| MX | `createMxConnectFixUrl(credentialId, isDarkMode, isMobileWebview)` | Direct MX/MoneyDesktop reconnect URL |
| Finicity | `createFinicityConnectFixUrl(credentialId)` | Direct Finicity reconnect URL |
| Plaid | `createPlaidLinkToken(credentialId, redirectUri)` then `syncCredentialAfterReconnect` after Link success | Link token, not a plain URL |

Use the provider-specific credential ID from Monarch accounts data. The user must complete bank credentials/MFA directly in the provider UI. Do not ask for or handle bank credentials.

## Included scripts

Run from the skill root:

```bash
cd /path/to/skills/monarch
python scripts/generate_monarch_reconnect_link.py "Institution name"
python scripts/generate_monarch_reconnect_link.py --credential-id CREDENTIAL_UUID
```

The account-health watcher is designed for no-agent cron/watchdog use:

```bash
cd /path/to/skills/monarch
HERMES_HOME=/path/to/hermes-profile python scripts/monarch_account_health_watch.py
```

Optional environment variables:

| Variable | Purpose |
|---|---|
| `MONARCH_PROFILE_HOME` / `HERMES_HOME` | Profile whose `.env` should be loaded for Telegram delivery vars |
| `MONARCH_HEALTH_STATE_PATH` | State file for alert de-duping; default `/tmp/monarch_account_health_watch_state.json` |
| `MONARCH_STALE_HOURS` | Account staleness threshold; default `72` |
| `MONARCH_REMIND_HOURS` | Reminder interval for unchanged unhealthy state; default `24` |

## Side-effect boundaries

- Generating a reconnect URL is a sensitive but expected repair action after the user asks to reconnect or monitor broken accounts.
- Scheduled watchers should **not** generate short-lived MX/Finicity reconnect URLs. Alert first; generate repair links only on demand while the user is online.
- Triggering account refresh/sync is side-effecting; confirm or rely on an explicit user request.
- Never paste bank credentials or ask the user to share them. Send provider-hosted links only.

## Link delivery pitfall

Telegram/Markdown can visually or actually truncate very long provider URLs. If a generated reconnect URL is long, prefer one of these delivery forms:

1. Write the full URL to `/tmp/<institution>_reconnect_url.txt` and send as `MEDIA:`.
2. Write a small HTML redirect file with `<meta http-equiv="refresh" ...>` and an anchor to the full URL, then send as `MEDIA:`.
3. If pasting inline, verify the rendered message does not contain literal `...` in the URL.

## Health watcher pattern

A no-agent cron script can keep account-health monitoring cheap and quiet:

- Query `monarch.py accounts --raw`.
- Group accounts by `credential.id` so one broken credential does not create duplicate alerts per account.
- Alert only when unhealthy state changes or after a reminder interval.
- Treat `credential.updateRequired`, `syncDisabled`, and provider-linked stale updates as unhealthy.
- Do **not** generate short-lived MX/Finicity reconnect URLs inside scheduled/overnight alerts. Notify that the credential is broken and include a reply instruction; generate the repair URL only on demand.
- For MX/Finicity, use `scripts/generate_monarch_reconnect_link.py` after the user asks.
- For Plaid, note that a Link token is not directly openable unless wrapped in a browser/UI flow.
- Stay silent when all accounts are healthy.

## Backfill caveat

`request_accounts_refresh` / `monarch.py refresh --wait --confirm` can complete successfully without recovering historical missing transactions. After reconnect or refresh, re-query the relevant date windows and compare expected transactions rather than assuming backfill happened.
