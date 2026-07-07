# dev-tools

Small CLI helpers for development workflows.

## PR triage

Install from a checkout:

```bash
uv tool install .
```

Run during development:

```bash
dev prs --project clemux/plant-manager
dev prs --project clemux/plant-manager --json
```

The command delegates all GitHub access and authentication to `gh`.
