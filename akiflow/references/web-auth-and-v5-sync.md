# Akiflow Web Auth + v5 Sync Notes

Session-derived notes for validating Akiflow's private web API before wiring or repairing Hermes-native tools.

## Live endpoint shape observed

Akiflow's current web app uses the v5 sync endpoints with large page limits and optional sync tokens. Example shape:

```text
GET https://api.akiflow.com/v5/labels?limit=2500&sync_token=<opaque-token>
```

The Hermes-native Akiflow client should use the same pattern for syncable resources:

- `https://api.akiflow.com/v5/tasks`
- `https://api.akiflow.com/v5/labels`
- `https://api.akiflow.com/v5/tags`
- `https://api.akiflow.com/v5/events`
- `https://api.akiflow.com/v5/calendars`
- `https://api.akiflow.com/v5/time_slots`

Use `limit=2500`; carry forward returned `sync_token`; if a cached token produces inconsistent results, retry once with no `sync_token` for a full refresh.

## Auth artifacts: what is and is not useful

- `Authorization: Bearer <JWT>` on `api.akiflow.com` calls is a real Akiflow access token, but observed JWTs are short-lived (~30 min). It can be used as `AKIFLOW_ACCESS_TOKEN` for smoke tests.
- `POST https://web.akiflow.com/oauth/refreshToken` with `{client_id:"10", refresh_token:"..."}` is the long-lived flow used by the upstream MCP to mint Bearer access tokens.
- `/api/pusherAuth` returns a Pusher `key:signature` for private websocket channel subscription (for example `private-user.<id>`). It is not API auth and cannot be transformed into a refresh token.
- `x-xsrf-token` / `XSRF-TOKEN` are browser CSRF protections for web-session requests, not Bearer or refresh credentials.
- `akiflow_web_*` cookies may represent encrypted web session state, but the Hermes client should not treat them as API tokens unless a future live browser inspection proves otherwise.

## Email-login link behavior

Akiflow email links of the form:

```text
https://web.akiflow.com/auth/email/<email>?expires=...&signature=...&salt=...
```

may still load the "Confirm your email" code form instead of magic-logging in. Live instrumentation showed the form POSTs JSON to the signed URL:

```http
POST https://web.akiflow.com/auth/email/<email>?expires=...&signature=...
Content-Type: application/json

{"email":"<email>","code":"000000"}
```

Invalid codes return:

```json
{"success":false,"message":"Invalid authentication code."}
```

Avoid repeatedly re-submitting the login email address while coordinating with the user; each new login attempt can generate a new code and invalidate older codes. If the user provides a direct signed email URL, navigate to it directly and use the code from that same email.

## Browser-network debugging pattern

When DevTools network details are not directly exposed, inject temporary fetch/XHR instrumentation in the browser console before submitting a form:

```js
(() => {
  const logs = [];
  window.__netlogs = logs;
  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    const req = args[0];
    const url = typeof req === 'string' ? req : req.url;
    const opts = args[1] || {};
    const body = opts.body || (req && req.body) || null;
    const res = await origFetch.apply(this, args);
    let txt = '';
    try { txt = (await res.clone().text()).slice(0, 1000); } catch (e) {}
    logs.push({ type: 'fetch', url, method: opts.method || (req && req.method) || 'GET', requestBody: String(body).slice(0, 500), status: res.status, response: txt });
    return res;
  };
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__m = m; this.__u = u; return origOpen.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (body) {
    this.addEventListener('loadend', () => logs.push({ type: 'xhr', url: this.__u, method: this.__m, requestBody: String(body).slice(0, 500), status: this.status, response: (this.responseText || '').slice(0, 1000) }));
    return origSend.apply(this, arguments);
  };
})();
```

Then inspect `window.__netlogs`. Redact secrets before reporting.