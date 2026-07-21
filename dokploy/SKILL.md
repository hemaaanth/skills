---
name: dokploy-deployment
description: Inspect, diagnose, and safely manage Dokploy application or Compose deployments through its API. Use for Dokploy deployment status, queues, logs, stuck deployments, or deployment cleanup. Require explicit confirmation before killing a process or removing a deployment, and keep API keys in the approved credential environment.
---

# Dokploy deployment operations

Use `scripts/deployment.sh` for every Dokploy API call. It requires these injected environment variables:

- `DOKPLOY_URL`: the HTTPS origin of the user's Dokploy instance, without a trailing slash.
- `DOKPLOY_API_KEY`: an API key with the narrowest viable access.

Never print either value, place it in a repository, or pass it as an argument when invoking the helper. When a scoped 1Password Environment is configured, run the helper through its project-environment runner. If one is not configured, ask the user to provision it rather than requesting a secret in chat.

## Safe workflow

1. Confirm the target application, Compose service, or server ID. Do not infer an ID from a similarly named resource.
2. Start read-only: list the target's deployments, inspect the queue, then retrieve logs for the selected deployment.
3. Diagnose the error before retrying or changing infrastructure. Preserve the deployment ID and a redacted error summary.
4. Before an operational change, confirm the exact target, expected effect, whether a deployment is active, and whether persistent data has a current, restoration-tested backup.
5. Require explicit user confirmation for a restart, redeploy, restore, or infrastructure change. Require the exact deployment ID for `kill` or `remove`. These actions are not retries and may discard useful diagnostic state.

## Commands

```bash
# List deployments for an application, Compose service, or server.
scripts/deployment.sh app <application-id>
scripts/deployment.sh compose <compose-id>
scripts/deployment.sh server <server-id>

# View centralized deployments and the queue.
scripts/deployment.sh all
scripts/deployment.sh queue

# List a supported target type, including schedule and backup deployments.
scripts/deployment.sh type <resource-id> <application|compose|server|schedule|previewDeployment|backup|volumeBackup>

# Read up to 10,000 log lines, defaulting to 100.
scripts/deployment.sh logs <deployment-id> [tail]
```

The deployment API authenticates with `x-api-key: <token>`. Read operations use `deployment.all`, `deployment.allByCompose`, `deployment.allByServer`, `deployment.allCentralized`, `deployment.queueList`, `deployment.allByType`, and `deployment.readLogs`.

## Diagnose before changing state

| Symptom | Read-only checks |
| --- | --- |
| 404 | Confirm the exact custom domain and its target application, then inspect the application's latest deployment and logs. |
| 502 | Confirm the configured port matches the application listener, that it binds to `0.0.0.0`, then inspect deployment logs. |
| Failed build | Read the selected deployment logs and report the earliest actionable error, not just the final exit code. |
| Stuck queue | Inspect `queue` and the target's deployment history. Do not kill a process until the user confirms its exact ID. |

After a confirmed deployment or routing change, re-list the target deployments, read fresh logs, request the public URL, and verify the expected HTTP status and TLS certificate. Redeploy after changing a Compose domain or deployment setting before treating the routing change as applied.

## Destructive operations

Use progressive authorization:

- Read-only diagnostics: no extra confirmation after the user identifies the target.
- Reversible operational changes: confirm the exact target and intended change immediately before execution.
- Destructive operations: confirm the exact deployment ID immediately before execution.

Only after exact user confirmation, run one of these commands with `--confirm`:

```bash
scripts/deployment.sh kill <deployment-id> --confirm
scripts/deployment.sh remove <deployment-id> --confirm
```

`kill` calls `POST /api/deployment.killProcess` and stops the active deployment process. `remove` calls `POST /api/deployment.removeDeployment` and removes the deployment record. State the chosen endpoint and deployment ID immediately before executing it, then re-list the queue or target deployments to verify the result. Never add broad cleanup, SSH, server-update, or secret-inspection commands to this skill.

## Application deployment checklist

Get the deployment origin from the user. Keep it consistent across build-time public variables, runtime configuration, DNS, external OAuth callback URLs, and post-deployment HTTP/TLS validation. Do not hard-code a production domain in this generic skill.

## Adapters

The skill is portable without adapters. The optional Hermes adapter at `adapters/hermes/` uses this CLI rather than duplicating request or credential logic.

## API reference

The supported endpoints and request parameters are verified against the [Dokploy deployment API](https://docs.dokploy.com/docs/api/deployment). Treat undocumented endpoints as out of scope.
