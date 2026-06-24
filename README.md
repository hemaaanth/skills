# Skills

A collection of curated, vetted, and custom-built skills for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Install

For Claude Code, install the repository directly:

```bash
/install-skill hemaaanth/skills
```

You can also use the open `skills` CLI via `npx`:

```bash
npx skills add hemaaanth/skills
```

In this command, `npx skills` runs the npm package named `skills`, and
`add hemaaanth/skills` tells that CLI to install skills from the GitHub
repository at `https://github.com/hemaaanth/skills`. Use `--list` to preview
what the CLI will find without installing anything:

```bash
npx skills add hemaaanth/skills --list
```

This adds all available skills from this repository to your agent environment.

## Available Skills

| Skill | Description |
|-------|-------------|
| **monarch** | Monarch Money personal finance API: check balances, transactions, budgets, cashflow, recurring expenses, and net worth. Code forked from https://github.com/hammem/monarchmoney |
| **akiflow** | Akiflow private API skill: tasks, projects, tags, calendar reads, time slots, Meeting Assistant recordings/action items, and meeting briefs via a portable JSON CLI. |

## Contributing

Skills live in top-level directories with a `SKILL.md` file and any supporting scripts or resources. To add a skill:

1. Create a new directory at the repo root
2. Add a `SKILL.md` with frontmatter (`name`, `description`) and usage instructions
3. Include any scripts or assets the skill needs
4. Open a PR

## License

MIT
