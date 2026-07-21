# Hermes adapter for the Dokploy deployment skill

This optional adapter exposes the portable Dokploy CLI as a native Hermes toolset. It has no request or credential logic of its own, so command-line and Hermes users receive the same input validation and destructive-operation guardrail.

## Local install

From the root of this skills repository:

```bash
ln -sfn /path/to/skills/dokploy/adapters/hermes/dokploy_tools.py \
  /path/to/hermes-agent/tools/dokploy_tools.py
```

Register and enable the `dokploy` toolset in Hermes, then restart Hermes or its gateway so the tool schema is loaded.

Set `DOKPLOY_SKILL_DIR=/path/to/skills/dokploy` only when the adapter is copied rather than symlinked. The Hermes process also needs the injected `DOKPLOY_URL` and `DOKPLOY_API_KEY` from its approved credential environment. Never put either value in tool registration, source code, or a committed `.env` file.

## Tool surface

- `dokploy_app_deployments`
- `dokploy_compose_deployments`
- `dokploy_server_deployments`
- `dokploy_all_deployments`
- `dokploy_deployment_queue`
- `dokploy_deployments_by_type`
- `dokploy_deployment_logs`
- `dokploy_kill_deployment(confirm=true)`
- `dokploy_remove_deployment(confirm=true)`

The final two tools require `confirm=true`, but the agent must still obtain explicit user confirmation of the exact deployment ID immediately before calling them.
