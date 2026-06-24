---
name: akiflow
description: Akiflow private API skill for agents. Use for Akiflow tasks, planning/scheduling, projects/labels, tags, calendar reads, time slots, Meeting Assistant recordings/action items, and meeting briefs from Claude Code, Codex, OpenClaw, Cursor, Hermes, or any file+shell agent.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [akiflow, tasks, calendar, productivity, meeting-assistant, private-api]
    related_skills: [hermes-local-toolsets]
---

# Akiflow

Akiflow task and calendar operations through Akiflow's private web APIs. This skill is portable: any agent that can read files and run shell commands can use `scripts/akiflow.py`. Optional native agent integrations should live under `adapters/<agent>/` and call the same `akiflow_client` package instead of duplicating API logic.

This repo version was folded out of the admin Hermes profile skill and is now the canonical source. The admin profile points back here through a skill symlink plus a tiny compatibility shim, so admin keeps working without a second active source of truth.

## Setup

From this skill directory:

```bash
cd skills/akiflow
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Credentials are not stored in this repo. Put one of these in the environment or the active Hermes profile `.env`:

```bash
AKIFLOW_REFRESH_TOKEN=<refresh_token from web.akiflow.com>
# temporary smoke-test fallback only:
AKIFLOW_ACCESS_TOKEN=<Bearer JWT access token, without the "Bearer " prefix>
```

For Hermes admin specifically, keep credentials in:

```text
/path/to/hermes-profile/.env
```

The preferred token is the Akiflow web refresh token. Access tokens are short-lived and are only useful for quick smoke tests.

## Quick Status

```bash
python scripts/akiflow.py status
python scripts/akiflow.py capabilities
```

All CLI commands output JSON. Use `--compact` before the subcommand for single-line JSON:

```bash
python scripts/akiflow.py --compact tasks --limit 10
```

## Read Commands

```bash
# Tasks
python scripts/akiflow.py tasks --limit 25
python scripts/akiflow.py tasks --done all --date-from 2026-06-01 --date-to 2026-06-30
python scripts/akiflow.py tasks --status 1      # Inbox
python scripts/akiflow.py tasks --status 2      # Planned
python scripts/akiflow.py tasks --status 10     # Scheduled

# Metadata
python scripts/akiflow.py projects
python scripts/akiflow.py tags

# Calendar/time-block reads
python scripts/akiflow.py calendars
python scripts/akiflow.py events --date-from 2026-06-22 --date-to 2026-06-29
python scripts/akiflow.py time-slots --date-from 2026-06-22 --date-to 2026-06-29

# Meeting Assistant
python scripts/akiflow.py recordings --limit 10
python scripts/akiflow.py recording RECORDING_ID
python scripts/akiflow.py meeting-briefs --limit 10
python scripts/akiflow.py meeting-brief BRIEF_ID
```

## Confirmed Write Commands

Never run write commands unless the user explicitly asks. Each write requires `--confirm`.

```bash
python scripts/akiflow.py create-task --title "Follow up" --date 2026-06-23 --duration 30 --confirm
python scripts/akiflow.py edit-task TASK_ID --title "New title" --confirm
python scripts/akiflow.py mark-done TASK_ID --confirm
python scripts/akiflow.py schedule-task TASK_ID --date 2026-06-23 --datetime 2026-06-23T16:00:00.000Z --duration 30 --confirm
python scripts/akiflow.py unschedule-task TASK_ID --confirm
python scripts/akiflow.py create-task-from-action-item RECORDING_ID ACTION_ITEM_ID --confirm
```

Event writes and time-slot create/update are intentionally not exposed in the portable CLI yet; use Google Calendar tooling for calendar writes unless the Akiflow path has been live-tested.

## API Map

See also `references/auth-and-api-observations.md` and `references/web-auth-and-v5-sync.md` for live auth/API findings.

| Capability | Endpoint family | Notes |
|---|---|---|
| Refresh token | `POST https://web.akiflow.com/oauth/refreshToken` | Body: `client_id=10`, `refresh_token`. Returns Bearer access token. |
| Tasks | `GET/PATCH https://api.akiflow.com/v5/tasks` | GET syncs with `sync_token`; PATCH accepts arrays of task records/partials. |
| Projects/labels | `GET https://api.akiflow.com/v5/labels` | Folders have `type='folder'`; projects/labels generally have `type=null`. |
| Tags | `GET/PATCH https://api.akiflow.com/v5/tags` | Uses v5 sync model. |
| Events | `GET https://api.akiflow.com/v5/events` | Read calendar events. Writes use v3 upstream and are not exposed here. |
| Calendars | `GET https://api.akiflow.com/v5/calendars` | Use to identify calendar IDs and read-only status. |
| Time slots | `GET/PATCH https://api.akiflow.com/v5/time_slots` | Internal Akiflow calendar blocks; do not sync as external calendar events. |
| Recordings | `GET https://aki.akiflow.com/api/v1/recordings` | Meeting Assistant recordings, summaries, action items, transcripts. |
| Action item -> task | `POST https://aki.akiflow.com/api/v1/recordings/createTaskFromActionItem/{recording_id}/{action_item_id}` | Creates an Akiflow task. |
| Meeting briefs | `GET https://aki.akiflow.com/api/v1/researches` | Pre-meeting research briefs. |

## Codes and Formats

### Task status

| Code | Meaning |
|---:|---|
| `1` | Inbox |
| `2` | Planned |
| `4` | Snoozed |
| `7` | Someday |
| `10` | Scheduled |

### Priority

| Code | Meaning |
|---:|---|
| `-1` | Goal |
| `1` | High |
| `2` | Medium |
| `3` | Low |
| `null` | None |

### Dates

- Dates: `YYYY-MM-DD`
- Datetimes: ISO 8601, e.g. `2026-01-26T10:00:00.000Z`
- CLI-facing durations are minutes; Akiflow stores task durations as seconds.

## Auth / Repair Notes

See the linked references for deeper notes:

- `references/browser-login-indexeddb-token.md` — current browser login and IndexedDB token extraction path.
- `references/auth-token-discovery.md` — why XSRF tokens, web cookies, and pusher auth are not API tokens.
- `references/web-auth-and-v5-sync.md` — live browser auth observations and v5 sync details.
- `references/auth-and-api-observations.md` — endpoint observations and status-code notes.
- `references/task-sizing-and-verification.md` — estimating and verifying Akiflow task durations.

## Agent Compatibility

| Agent | How to use |
|---|---|
| Claude Code | Install `hemaaanth/skills`, load this skill, run `python scripts/akiflow.py ...` from the skill directory. |
| Codex / OpenClaw / Cursor | Same file+shell workflow; inspect `SKILL.md`, then use the CLI. |
| Hermes | Admin native tools now use `akiflow/adapters/hermes/akiflow_tools.py` and `akiflow_client` from this repo. Other profiles can use the portable CLI or the same adapter pattern. |

## Pitfalls

1. **No credential in active environment:** `status` only checks whether a token is discoverable. API calls require `AKIFLOW_REFRESH_TOKEN` or a non-expired `AKIFLOW_ACCESS_TOKEN`.
2. **Access token mode is temporary:** Bearer JWTs expire quickly; use refresh tokens for unattended work.
3. **Pusher/XSRF/cookies are not API auth:** `/api/pusherAuth`, `x-xsrf-token`, `XSRF-TOKEN`, and normal web cookies are not substitutes for the refresh token.
4. **Profile confusion in Hermes:** use the target profile's `.env`; admin credentials live under `/path/to/hermes-profile/.env`.
5. **Private API fragility:** Akiflow does not document these endpoints publicly. If calls fail, inspect current web app network traffic and update headers/endpoints/client version.
6. **Write safety:** never run write commands without explicit user approval and `--confirm`.
7. **Do not commit secrets:** never add `.env`, cache files, tokens, cookies, or raw API responses containing personal data.

## Verification Checklist

- [ ] `python -m py_compile akiflow_client/client.py scripts/akiflow.py` passes.
- [ ] `python scripts/akiflow.py status` returns JSON.
- [ ] With credentials loaded, `python scripts/akiflow.py tasks --limit 5` succeeds before any write call.
- [ ] Write commands require explicit `--confirm`.
- [ ] Admin Hermes profile still has its profile-local Akiflow runtime files and skill.
