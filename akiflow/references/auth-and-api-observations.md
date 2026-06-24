# Akiflow Auth and API Observations

Session-derived notes for maintaining the Hermes-native Akiflow toolset. Do not store raw tokens, cookies, passwords, or full JWTs here.

## Live v5 API shape

The live Akiflow web app was observed calling the same v5 sync endpoints used by the Hermes-native client, e.g.:

```text
GET https://api.akiflow.com/v5/labels?limit=2500&sync_token=<base64-ish sync token>
```

This matches the toolset's `_sync_v5(...)` pattern:

- `limit=2500`
- optional `sync_token` from prior response
- response carries `data`, `sync_token`, and pagination flags

Core endpoint families used by the native toolset:

| Capability | Endpoint |
|---|---|
| Tasks | `GET/PATCH https://api.akiflow.com/v5/tasks` |
| Projects/labels | `GET https://api.akiflow.com/v5/labels?limit=2500&sync_token=...` |
| Tags | `GET https://api.akiflow.com/v5/tags?limit=2500&sync_token=...` |
| Events | `GET https://api.akiflow.com/v5/events?limit=2500&sync_token=...` |
| Calendars | `GET https://api.akiflow.com/v5/calendars?limit=2500&sync_token=...` |
| Time slots | `GET https://api.akiflow.com/v5/time_slots?limit=2500&sync_token=...` |
| Meeting recordings | `GET https://aki.akiflow.com/api/v1/recordings?per_page=100` |
| Recording detail | `GET https://aki.akiflow.com/api/v1/recordings/{id}` |
| Meeting briefs | `GET https://aki.akiflow.com/api/v1/researches?per_page=100` |
| Action item -> task | `POST https://aki.akiflow.com/api/v1/recordings/createTaskFromActionItem/{recording_id}/{action_item_id}` |

## Auth tokens encountered

Akiflow API requests use:

```http
Authorization: Bearer <JWT access token>
```

Observed Bearer JWTs had:

- `iss = https://web.akiflow.com`
- `aud = 10`
- short lifetime around 30 minutes

Therefore the native toolset supports two credential modes:

1. Preferred: `AKIFLOW_REFRESH_TOKEN` — used to mint fresh Bearer access tokens.
2. Temporary smoke-test fallback: `AKIFLOW_ACCESS_TOKEN` — direct Bearer JWT, with or without the `Bearer ` prefix, expected to expire quickly.

## Things that are not API credentials

Do not configure these as Hermes credentials:

- `x-xsrf-token` / `XSRF-TOKEN`: CSRF/session protection for browser requests.
- Akiflow web cookies such as `akiflow_web_token`, `akiflow_web_session`, `akiflow_web_auth_user`: likely encrypted web-session cookies, not v5 Bearer/refresh tokens.
- `POST https://web.akiflow.com/api/pusherAuth` response `{auth:"key:signature"}`: private Pusher/websocket channel authorization only; cannot derive a refresh token from it.
- Cloudflare/Stripe/analytics cookies.

## Browser/network workflow

When auth details are unclear, inspect the live app rather than relying only on upstream MCP code:

1. Use browser DevTools/Network with Preserve Log enabled.
2. Filter for `api.akiflow.com`, `aki.akiflow.com`, `oauth`, `refresh`, `token`, `Authorization`, and `Bearer`.
3. Confirm whether calls contain `Authorization: Bearer ...` and whether a preceding request minted that token.
4. If login code flow is used, enter each digit into its own OTP field; entering the whole code in the first field can fail.
5. If a reload/new login attempt was triggered, assume Akiflow may have emailed a new code and invalidated the previous one.

## Security notes

- Treat refresh tokens, access tokens, cookies, login codes, and passwords as secrets.
- Never repeat raw values back to the user or write them to skills/memory.
- If a secret was pasted into chat, recommend rotating/logging out when appropriate.
