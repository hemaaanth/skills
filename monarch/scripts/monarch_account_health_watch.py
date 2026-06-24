#!/usr/bin/env python3
"""Watch Monarch connected-account health and print alerts only when action is needed.

Runs under Hermes cron as no_agent=true. Keeps small state in /tmp to avoid spam.
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import urllib.request
from collections import defaultdict

REPO = pathlib.Path(os.getenv('MONARCH_SKILL_DIR', pathlib.Path(__file__).resolve().parents[1])).expanduser().resolve()
PROFILE_HOME = pathlib.Path(os.getenv('MONARCH_PROFILE_HOME') or os.getenv('HERMES_HOME') or pathlib.Path.home() / '.hermes').expanduser()
STATE_PATH = pathlib.Path(os.getenv('MONARCH_HEALTH_STATE_PATH', '/tmp/monarch_account_health_watch_state.json')).expanduser()
STALE_HOURS = int(os.getenv('MONARCH_STALE_HOURS', '72'))
REMIND_HOURS = int(os.getenv('MONARCH_REMIND_HOURS', '24'))


def load_profile_env():
    env_path = PROFILE_HOME / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(errors='ignore').splitlines():
        if not line or line.lstrip().startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


load_profile_env()


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse_dt(s):
    if not s:
        return None
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        x = dt.datetime.fromisoformat(s)
        if x.tzinfo is None:
            x = x.replace(tzinfo=dt.timezone.utc)
        return x.astimezone(dt.timezone.utc)
    except Exception:
        return None


def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, sort_keys=True))


def send_telegram_button(text, unhealthy):
    """Best-effort Telegram alert with on-demand reconnect buttons.

    The scheduled watcher should not generate short-lived reconnect URLs. Buttons
    carry the Monarch credential id; the gateway callback handler generates the
    URL only after the user taps.
    """
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_HOME_CHANNEL', '').strip()
    if not token or not chat_id:
        return False
    buttons = []
    for item in unhealthy:
        if item['provider'] in {'mx', 'finicity'}:
            label = f"Generate link: {item['institution']}"
            if len(label) > 60:
                label = label[:57] + '...'
            buttons.append([{'text': label, 'callback_data': f"mr:{item['credential_id']}"}])
    if not buttons:
        return False
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True,
        'reply_markup': {'inline_keyboard': buttons},
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return 200 <= resp.status < 300


def python_executable():
    venv_python = REPO / '.venv' / 'bin' / 'python'
    return str(venv_python if venv_python.exists() else sys.executable)


def run_accounts():
    out = subprocess.check_output(
        [python_executable(), 'scripts/monarch.py', 'accounts', '--raw'],
        cwd=REPO,
        text=True,
        stderr=subprocess.DEVNULL,
    )
    return json.loads(out)['accounts']


def summarize_credential(cred_id, rows):
    first = rows[0]
    cred = first.get('credential') or {}
    inst = (first.get('institution') or cred.get('institution') or {})
    provider = (first.get('dataProvider') or cred.get('dataProvider') or '').lower()
    latest = max([r.get('displayLastUpdatedAt') or '' for r in rows] or [''])
    update_required = any((r.get('credential') or {}).get('updateRequired') is True for r in rows)
    sync_disabled = any(r.get('syncDisabled') for r in rows)
    stale = False
    latest_dt = parse_dt(latest)
    if latest_dt:
        stale = (now_utc() - latest_dt) > dt.timedelta(hours=STALE_HOURS)
    # Ignore manual/offline accounts without credentials.
    reasons = []
    if update_required:
        reasons.append('login/update required')
    if sync_disabled:
        reasons.append('sync disabled')
    if stale and provider in {'mx', 'plaid', 'finicity'}:
        reasons.append(f'no update in >{STALE_HOURS}h')
    return {
        'credential_id': cred_id,
        'institution': inst.get('name') or 'Unknown institution',
        'provider': provider or 'unknown',
        'accounts': len(rows),
        'latest': latest,
        'reasons': reasons,
        'update_required': update_required,
    }


def main():
    state = load_state()
    accounts = run_accounts()
    by_cred = defaultdict(list)
    for a in accounts:
        cred = a.get('credential') or {}
        cred_id = cred.get('id')
        if not cred_id or a.get('isManual'):
            continue
        by_cred[cred_id].append(a)

    unhealthy = [summarize_credential(cid, rows) for cid, rows in by_cred.items()]
    unhealthy = [x for x in unhealthy if x['reasons']]
    unhealthy.sort(key=lambda x: (x['institution'], x['provider']))

    # Reset state when healthy, and stay silent.
    if not unhealthy:
        if state.get('last_unhealthy'):
            print('Monarch account health: all connected accounts look healthy again.')
        save_state({'last_unhealthy': [], 'last_alert_at': None})
        return

    signature = sorted((x['credential_id'], tuple(x['reasons'])) for x in unhealthy)
    sig_json = json.dumps(signature, sort_keys=True)
    last_sig = state.get('last_signature')
    last_alert = parse_dt(state.get('last_alert_at'))
    should_alert = sig_json != last_sig or not last_alert or (now_utc() - last_alert) > dt.timedelta(hours=REMIND_HOURS)
    if not should_alert:
        save_state(state)
        return

    lines = ['## Monarch account health alert', '', 'I found unhealthy connected account credentials:']
    for item in unhealthy:
        lines += [
            '',
            f"### {item['institution']}",
            f"- Provider: `{item['provider']}`",
            f"- Accounts affected: **{item['accounts']}**",
            f"- Latest account update: `{item['latest'] or 'unknown'}`",
            f"- Reason: **{', '.join(item['reasons'])}**",
        ]
        if item['provider'] in {'mx', 'finicity'}:
            lines.append(f"- Reconnect: tap the button below, or reply **generate Monarch reconnect link for {item['institution']}**, and I’ll create a fresh short-lived link while you’re online.")
        elif item['provider'] == 'plaid':
            lines.append('- Reconnect: Plaid requires an interactive Link flow. Open Monarch → Institutions → Update login settings for this connection.')
        else:
            lines.append(f"- Reconnect: no direct reconnect URL support for provider `{item['provider']}` in this watcher.")

    state['last_signature'] = sig_json
    state['last_alert_at'] = now_utc().isoformat()
    state['last_unhealthy'] = unhealthy
    save_state(state)
    text = '\n'.join(lines)
    try:
        if send_telegram_button(text, unhealthy):
            return
    except Exception:
        pass
    print(text)


if __name__ == '__main__':
    main()
