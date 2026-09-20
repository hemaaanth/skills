---
name: linear-cli
description: "Use the JSON-first `linear-cli` to search and manage Goldsky Linear projects, issues, comments, documents, cycles, and milestones. Use only when the current Git repository's origin belongs to `goldsky-io`."
---

# Linear CLI

Before any Linear call, verify scope:

```sh
git remote get-url origin | rg '(^|[/:])goldsky-io/'
```

Stop outside a Goldsky-owned repository.

Check authentication with `linear-cli auth status`. Use `linear-cli --help` and subcommand help instead of guessing flags; output is JSON.

Common reads:

```sh
linear-cli issue list --query 'search terms'
linear-cli issue get --id GLD-123 --include-relations
linear-cli project list --query 'project name'
linear-cli comment list --issue-id GLD-123
```

Only write when the user explicitly requests it. Read the target first, preserve fields the user did not ask to change, then use `issue save`, `comment save`, `project save`, or the relevant command.

Never pass an API key on the command line. Use the persisted OAuth login or `LINEAR_API_KEY` from a scoped environment.
