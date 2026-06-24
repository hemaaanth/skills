# Akiflow Auth Token Discovery Notes

## What Hermes Akiflow tools accept

Prefer:

```bash
AKIFLOW_REFRESH_TOKEN=<long-lived refresh_token>
```

Fallback for smoke tests:

```bash
AKIFLOW_ACCESS_TOKEN=<short-lived JWT access token>
```

The native client accepts either. `AKIFLOW_REFRESH_TOKEN` is durable because it can call `/oauth/refreshToken` and obtain new Bearer access tokens. `AKIFLOW_ACCESS_TOKEN` is useful for immediate validation only; observed Akiflow JWTs expire after about 30 minutes.

## Confirmed API auth shape

The upstream MCP and live browser traffic indicate Akiflow API calls use:

```http
Authorization: Bearer <JWT access_token>
```

The upstream MCP refresh flow is:

```http
POST https://web.akiflow.com/oauth/refreshToken
Content-Type: application/json

{"client_id":"10","refresh_token":"<refresh token>"}
```

Response contains `access_token`, which becomes the Bearer token for `api.akiflow.com` / `aki.akiflow.com` calls.

## Token candidates and interpretation

| Candidate | Meaning | Use in Hermes? |
|---|---|---|
| `Authorization: Bearer <JWT>` on API calls | Short-lived Akiflow API access token | Yes, as `AKIFLOW_ACCESS_TOKEN`, for smoke tests only |
| `refresh_token` in `/oauth/refreshToken` payload | Long-lived token that mints access JWTs | Yes, preferred as `AKIFLOW_REFRESH_TOKEN` |
| `x-xsrf-token` / `XSRF-TOKEN` cookie | CSRF protection for browser web session/login | No |
| `akiflow_web_token`, `akiflow_web_session`, `akiflow_web_auth_user` | Encrypted/scoped web cookies | Not currently accepted; do not assume they are refresh tokens |
| `/api/pusherAuth` response `{auth:"key:signature"}` | Pusher private-channel websocket auth | No; cannot derive refresh token from it |
| Cloudflare / Stripe / analytics cookies | Vendor/session/analytics cookies | No |

## Practical DevTools search workflow

1. Open `https://web.akiflow.com` and DevTools -> Network.
2. Enable **Preserve log** and filter to Fetch/XHR.
3. Search for:
   - `refresh`
   - `oauth`
   - `token`
   - `api.akiflow.com`
   - `aki.akiflow.com`
   - `Authorization`
   - `Bearer`
4. Inspect requests to:
   - `https://api.akiflow.com/v5/tasks`
   - `https://api.akiflow.com/v5/labels`
   - `https://api.akiflow.com/v5/events`
   - `https://aki.akiflow.com/api/v1/recordings`
5. If an API request has `Authorization: Bearer ...`, copy only the JWT portion into `AKIFLOW_ACCESS_TOKEN` for a short smoke test.
6. Keep hunting for the request that minted that JWT. It should correspond to `/oauth/refreshToken` or equivalent and expose the durable `refresh_token`.

## Security handling

- Never ask the user to paste live cookies, JWTs, refresh tokens, or credentials into chat.
- If the user already pasted a credential, do not repeat it; refer to it by type only.
- Prefer instructing the user to place secrets directly in the active profile `.env`.
- Treat `AKIFLOW_ACCESS_TOKEN` as exposed and short-lived; rotate by logging out/in if it was pasted.

## Testing pattern

After adding a token to `/path/to/hermes-profile/.env`, restart/reload the session and test reads before writes:

```python
# Expected safe first call through Hermes tool dispatch:
akiflow_list_tasks(limit=1)
```

If testing at the Python layer, ensure `HERMES_HOME=/path/to/hermes-profile` so the backend reads the admin profile `.env`.
