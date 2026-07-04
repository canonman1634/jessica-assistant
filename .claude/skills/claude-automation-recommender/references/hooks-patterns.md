# Hooks Patterns Reference

Hooks run shell commands automatically in response to tool events, configured in `.claude/settings.json`.

## Common Hook Events

- `PreToolUse` — runs before a tool call; can block it (exit non-zero / structured deny)
- `PostToolUse` — runs after a tool call succeeds
- `SessionStart` / `Stop` — session lifecycle

## Format-on-Edit

Signal: `.prettierrc*`, `prettier` in devDependencies

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "npx prettier --write \"$CLAUDE_TOOL_FILE_PATH\""}]
      }
    ]
  }
}
```

## Lint-on-Edit

Signal: `.eslintrc*` / `ruff.toml` / `pyproject.toml` with `[tool.ruff]`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "npx eslint --fix \"$CLAUDE_TOOL_FILE_PATH\""}]
      }
    ]
  }
}
```

## Type-Check on Edit

Signal: `tsconfig.json`

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "npx tsc --noEmit"}]
      }
    ]
  }
}
```

## Run Related Tests on Edit

Signal: `tests/` or `__tests__/` directory exists

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "scripts/run-related-tests.sh \"$CLAUDE_TOOL_FILE_PATH\""}]
      }
    ]
  }
}
```

## Block Sensitive File Edits

Signal: `.env`, `.env.*`, secrets files present

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "scripts/block-env-edits.sh"}]
      }
    ]
  }
}
```

The script should inspect `$CLAUDE_TOOL_FILE_PATH` and exit non-zero (with a message on stderr) if it matches a
protected pattern like `.env*` or `*.pem`.

## Block Lock File Edits

Signal: `package-lock.json`, `yarn.lock`, `poetry.lock`, `Cargo.lock` present

Same shape as above, matching lock file paths — prevents Claude from hand-editing generated files instead of
running the package manager.

## Require Confirmation for Security-Sensitive Paths

Signal: `auth/`, `payments/`, `crypto/` directories, or files matching `*auth*`, `*payment*`

Use a `PreToolUse` hook that returns a permission prompt (rather than a hard block) so changes to
security-critical code always get a human look before applying.

## General Guidance

- Prefer hooks that call an existing project script (`npm run lint`, `make test`) over hand-rolled shell logic — reuse what the team already trusts.
- Keep hook commands fast; slow hooks make every tool call sluggish.
- Only recommend blocking hooks (`PreToolUse` denials) for genuinely irreversible or sensitive operations — over-blocking degrades trust in the tool.
