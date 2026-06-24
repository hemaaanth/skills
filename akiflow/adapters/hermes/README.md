# Hermes adapter for the Akiflow skill

This optional adapter exposes Akiflow as a native Hermes toolset while keeping the portable skill repo as the canonical source of truth.

## Canonical layout

```text
/path/to/skills/akiflow/
  SKILL.md
  akiflow_client/          # canonical private API client
  scripts/akiflow.py       # portable JSON CLI for Claude Code/Codex/OpenClaw/Cursor
  adapters/hermes/         # native Hermes adapter shim
```

## Local install

From the root of the skills repo:

```bash
ln -sfn /path/to/skills/akiflow/adapters/hermes/akiflow_tools.py \
  /path/to/hermes-agent/tools/akiflow_tools.py
```

Hermes then imports this adapter, and this adapter imports `akiflow_client` from the shared skill repo. Do not duplicate Akiflow business logic inside `~/.hermes/hermes-agent/tools/`.

## Admin profile compatibility

The admin profile can keep its existing toolset registration and credentials. Its old profile-local backend path is kept as a compatibility shim:

```text
/path/to/hermes-profile/akiflow/akiflow_api.py
```

That shim imports the canonical `akiflow_client` from this repo. The active admin skill directory should point at this repo too:

```text
/path/to/hermes-profile/skills/productivity/akiflow -> /path/to/skills/akiflow
```

## Secrets

Tokens stay in the active profile `.env`, e.g.:

```text
/path/to/hermes-profile/.env
```

Never commit `.env`, cache files, refresh tokens, access tokens, cookies, or raw personal API payloads.
