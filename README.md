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

Save a project as the default for later runs:

```bash
dev prs --project clemux/plant-manager --save-project-default
dev prs
```

The default project is stored in `dev-tools/config.json` under `$XDG_CONFIG_HOME`, or under
`~/.config` when `XDG_CONFIG_HOME` is unset.

The command delegates all GitHub access and authentication to `gh`.
