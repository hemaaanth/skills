# Hermes adapter for the Monarch skill

This optional adapter exposes a read-oriented Monarch Money toolset in Hermes while keeping the skill portable for other agents.

## Local install

From the root of this skills repo:

```bash
cp monarch/adapters/hermes/monarch_tools.py ~/.hermes/hermes-agent/tools/monarch_tools.py
```

Then add a `monarch` toolset entry to your Hermes installation (`toolsets.py` and `hermes_cli/tools_config.py`), enable it, and restart Hermes/gateway so the new tool schema is loaded.

The adapter imports the same `monarch_client` package used by `scripts/monarch.py`. If you copy only the adapter file, make sure `monarch/` is on `PYTHONPATH` or install/symlink the skill directory where Hermes can import it.

## Tool surface

The adapter intentionally starts with read tools plus confirmed refresh:

- `monarch_status`
- `monarch_accounts`
- `monarch_transactions`
- `monarch_budgets`
- `monarch_cashflow`
- `monarch_recurring`
- `monarch_networth`
- `monarch_refresh_accounts(confirm=true)`

Broader write tools should be added only after the local user explicitly enables them.
