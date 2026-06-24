#!/usr/bin/env python3
"""Generate an on-demand Monarch reconnect URL for an unhealthy credential.

Usage:
  generate_monarch_reconnect_link.py "Wealthsimple"
  generate_monarch_reconnect_link.py --credential-id UUID
"""
import argparse
import asyncio
import json
import os
import pathlib
import subprocess
import sys
from collections import defaultdict

from gql import gql

REPO = pathlib.Path(os.getenv('MONARCH_SKILL_DIR', pathlib.Path(__file__).resolve().parents[1])).expanduser().resolve()


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


def account_institution(account):
    cred = account.get('credential') or {}
    inst = account.get('institution') or cred.get('institution') or {}
    return inst.get('name') or 'Unknown institution'


def choose_credential(accounts, query=None, credential_id=None):
    grouped = defaultdict(list)
    for account in accounts:
        cred = account.get('credential') or {}
        cid = cred.get('id')
        if cid and not account.get('isManual'):
            grouped[cid].append(account)

    candidates = []
    q = (query or '').lower().strip()
    for cid, rows in grouped.items():
        first = rows[0]
        cred = first.get('credential') or {}
        provider = (first.get('dataProvider') or cred.get('dataProvider') or '').lower()
        institution = account_institution(first)
        if credential_id and cid != credential_id:
            continue
        if q and q not in institution.lower():
            continue
        candidates.append({'credential_id': cid, 'provider': provider, 'institution': institution, 'accounts': len(rows)})

    if not candidates:
        raise SystemExit('No matching Monarch credential found.')
    if len(candidates) > 1:
        lines = ['Multiple matching credentials found; be more specific:']
        for c in candidates:
            lines.append(f"- {c['institution']} ({c['provider']}), credential_id={c['credential_id']}")
        raise SystemExit('\n'.join(lines))
    return candidates[0]


async def get_graphql_client():
    sys.path.insert(0, str(REPO))
    from monarch_client.client import MonarchClient
    return MonarchClient()._client()


async def make_reconnect_artifact(client, provider, credential_id):
    provider = (provider or '').lower()
    if provider == 'mx':
        q = gql('''mutation Common_CreateMXConnectFixUrlMutation($credentialId: UUID!, $isDarkMode: Boolean, $isMobileWebview: Boolean) {
          createMxConnectFixUrl(credentialId: $credentialId, isDarkMode: $isDarkMode, isMobileWebview: $isMobileWebview) {
            url
            errors { message code fieldErrors { field messages } }
          }
        }''')
        data = await client.gql_call(
            operation='Common_CreateMXConnectFixUrlMutation',
            graphql_query=q,
            variables={'credentialId': credential_id, 'isDarkMode': False, 'isMobileWebview': False},
        )
        res = data.get('createMxConnectFixUrl') or {}
        return {'kind': 'url', 'url': res.get('url'), 'errors': res.get('errors')}

    if provider == 'finicity':
        q = gql('''mutation Common_CreateFinicityConnectFixUrlMutation($credentialId: UUID!) {
          createFinicityConnectFixUrl(credentialId: $credentialId) {
            url
            errors { message code fieldErrors { field messages } }
          }
        }''')
        data = await client.gql_call(
            operation='Common_CreateFinicityConnectFixUrlMutation',
            graphql_query=q,
            variables={'credentialId': credential_id},
        )
        res = data.get('createFinicityConnectFixUrl') or {}
        return {'kind': 'url', 'url': res.get('url'), 'errors': res.get('errors')}

    if provider == 'plaid':
        return {'kind': 'plaid', 'message': 'Plaid needs an interactive Link UI. Open Monarch → Institutions → Update login settings.'}
    return {'kind': 'unsupported', 'provider': provider}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('query', nargs='?', help='Institution name substring, e.g. Wealthsimple')
    parser.add_argument('--credential-id')
    args = parser.parse_args()

    selected = choose_credential(run_accounts(), query=args.query, credential_id=args.credential_id)
    artifact = await make_reconnect_artifact(await get_graphql_client(), selected['provider'], selected['credential_id'])
    print(f"## Monarch reconnect link for {selected['institution']}")
    print(f"Provider: `{selected['provider']}`")
    print('')
    if artifact.get('kind') == 'url' and artifact.get('url'):
        print(f"[Open secure reconnect link]({artifact['url']})")
        print('')
        print('This link was generated on demand and may expire soon.')
    elif artifact.get('kind') == 'plaid':
        print(artifact['message'])
    else:
        print(f"Could not generate a direct reconnect URL: `{artifact}`")


if __name__ == '__main__':
    asyncio.run(main())
