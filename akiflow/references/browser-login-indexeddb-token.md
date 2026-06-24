# Akiflow browser login + IndexedDB token extraction

Use this when browser/API validation is needed or the user provides an Akiflow email verification link.

## Durable findings

- Akiflow email links of the form `https://web.akiflow.com/auth/email/<email>?expires=...&signature=...&salt=...` may **not** auto-login. They can render the code-entry page and submit the code to the same URL.
- Do **not** restart the login flow after the user gives a code unless necessary; submitting the email again can generate a new code and invalidate the one the user just supplied.
- After successful login, the app redirects to `https://web.akiflow.com/#/planner/today` and performs current v5 sync calls such as:
  - `GET https://api.akiflow.com/v5/clients`
  - `GET https://api.akiflow.com/v5/user/settings`
  - `GET https://api.akiflow.com/v5/accounts?limit=2500`
  - `GET https://api.akiflow.com/v5/labels?limit=2500`
  - `GET https://api.akiflow.com/v5/tasks?limit=2500`
  - `GET https://api.akiflow.com/v5/tags?limit=2500`
  - `GET https://api.akiflow.com/v5/time_slots?limit=2500`
  - `GET https://api.akiflow.com/v5/contacts?limit=2500`
  - `GET https://api.akiflow.com/v5/calendars?limit=2500`
  - `GET https://api.akiflow.com/v5/events?limit=2500`
  - `GET https://api.akiflow.com/v5/event_modifiers?limit=2500`
- Akiflow stores the account OAuth material in browser IndexedDB, not normal cookies:
  - DB: `akiflow_system`
  - Store: `local_accounts_data`
  - Fields include `access_token`, `refresh_token`, `token_type: Bearer`, `expires_in: 1800`, `accountId`, and user metadata.
- `POST https://web.akiflow.com/oauth/refreshToken` with body `{client_id:"10", refresh_token:"..."}` returns a fresh short-lived access token. This access token works against `https://api.akiflow.com/v5/...` with `Authorization: Bearer <access>`.

## Recommended workflow

1. If the user provides an email verification link, navigate directly to that link. Do **not** go to `/auth/login` unless the link is expired or unusable.
2. Before entering a code, optionally install a fetch/XHR logger so failed/success calls are visible. Redact codes/tokens in outputs.
3. Enter the exact current code once; avoid parallel/repeated login attempts.
4. After successful login, immediately extract `refresh_token` from IndexedDB and persist it to the active profile `.env` before leaving/navigating the page. Do not only print a redacted confirmation; the raw value can be lost if the browser context resets.
5. Verify with two live calls:
   - `POST /oauth/refreshToken` returns 200 and `access_token`.
   - `GET /v5/labels?limit=5` returns 200 with `data`, `sync_token`, and `has_next_page`.
6. Restart/reset Hermes so tool schemas re-discover with `AKIFLOW_REFRESH_TOKEN` present.

## Browser snippets

List IndexedDB stores:

```js
indexedDB.databases().then(async dbs => {
  const out = {};
  for (const d of dbs) {
    await new Promise(res => {
      const req = indexedDB.open(d.name);
      req.onsuccess = () => {
        const db = req.result;
        out[d.name] = Array.from(db.objectStoreNames);
        db.close();
        res();
      };
      req.onerror = () => res();
    });
  }
  return out;
});
```

Extract account data. For chat output, redact token fields; for writing `.env`, pass the raw `refresh_token` directly to the file write/edit operation and do not expose it in the final response.

```js
new Promise(resolve => {
  const open = indexedDB.open('akiflow_system');
  open.onsuccess = () => {
    const db = open.result;
    const tx = db.transaction(['local_accounts_data'], 'readonly');
    const st = tx.objectStore('local_accounts_data');
    const g = st.getAll();
    g.onsuccess = () => {
      const acct = (g.result || [])[0] || {};
      db.close();
      resolve({
        email: acct.email,
        accountId: acct.accountId,
        refresh_token: acct.refresh_token,
        access_token_present: !!acct.access_token,
      });
    };
    g.onerror = () => resolve({error: 'getAll failed'});
  };
  open.onerror = () => resolve({error: 'open failed'});
});
```

Live refresh + labels smoke test from the browser:

```js
// after assigning refresh from IndexedDB
const r = await fetch('https://web.akiflow.com/oauth/refreshToken', {
  method: 'POST',
  headers: {'Accept': 'application/json', 'Content-Type': 'application/json'},
  body: JSON.stringify({client_id: '10', refresh_token: refresh})
});
const body = await r.json();
const labels = await fetch('https://api.akiflow.com/v5/labels?limit=5', {
  headers: {
    'Accept': 'application/json',
    'Authorization': 'Bearer ' + body.access_token,
    'Akiflow-Platform': 'mac',
    'Akiflow-Client-Id': 'b4edaac3-5dc7-4b20-bf58-de51efc2bec4',
    'Akiflow-Version': '2.71.5'
  }
});
await labels.json();
```
