# MCP Server Reference

Detailed patterns for recommending MCP servers based on codebase signals.

## Documentation & Library Lookup

**context7**
- Signal: any project with third-party dependencies (npm, pip, cargo, etc.) where docs go stale fast
- Value: pulls current, version-matched docs/examples instead of relying on training data
- Install: `claude mcp add context7`

## Browser / Frontend Testing

**Playwright**
- Signal: `playwright.config.*`, `@playwright/test` dependency, or a frontend app with no E2E coverage
- Value: drive the real UI, take screenshots, verify flows end-to-end
- Install: `claude mcp add playwright`

## Databases

**Supabase MCP**
- Signal: `@supabase/supabase-js` dependency, `supabase/` config directory
- Value: run queries, inspect schema, manage migrations without leaving the session

**Convex MCP**
- Signal: `convex/` directory, `convex` dependency
- Value: introspect live deployment, run queries/mutations, read logs and env vars

**Generic database MCP (Postgres/MySQL)**
- Signal: `DATABASE_URL`, `pg`/`mysql2`/`psycopg2` dependency, raw SQL migrations
- Value: schema introspection and query execution against the real database

## Version Control & Project Management

**GitHub MCP**
- Signal: `.git` remote pointing to github.com, `.github/workflows/`
- Value: manage issues/PRs, inspect CI runs, review diffs without shelling out to `gh`

**Linear MCP**
- Signal: `LINEAR_` env vars, issue keys in commit messages (e.g. `ENG-123`)
- Value: read/update tickets tied to the work being done

## Team Communication

**Slack MCP**
- Signal: Slack webhook URLs, `@slack/bolt` or `@slack/web-api` dependency
- Value: post build/test/deploy notifications directly from a session

## Infrastructure

**AWS MCP**
- Signal: `aws-sdk`, `boto3`, Terraform/CDK/SAM files targeting AWS
- Value: inspect and manage cloud resources without a separate CLI session

**Docker MCP**
- Signal: `Dockerfile`, `docker-compose.yml`
- Value: manage containers/images/logs during local development

## Observability

**Sentry MCP**
- Signal: `@sentry/*` or `sentry-sdk` dependency, `SENTRY_DSN`
- Value: pull real error events/stack traces into the session for triage

## Cross-Session Memory

**Memory MCP**
- Signal: recurring multi-day projects, user asks Claude to "remember" things across sessions
- Value: persist facts/preferences outside the conversation window

## General Guidance

- Prefer recommending MCP servers that map to dependencies *actually present* in the repo — don't suggest Supabase MCP for a project with no Supabase client.
- Check `.mcp.json` for servers already configured before recommending duplicates.
- For internal/custom APIs with no off-the-shelf MCP server, note that a thin custom MCP server (via the MCP SDK) may be worth building — point to the `mcp-builder` plugin/skill if available.
