# Subagent Templates Reference

Subagents live in `.claude/agents/<name>.md` and run with their own context window and tool access,
useful for specialized or parallel work that shouldn't pollute the main conversation.

## Frontmatter

```yaml
---
name: agent-name
description: What this agent does and when the main agent should delegate to it
tools: Read, Grep, Glob   # restrict to what's actually needed
model: sonnet             # optional override
---
```

## code-reviewer

- Signal: large codebase (500+ files), team wants consistent review standards
- Purpose: reviews a diff for correctness bugs and simplification opportunities, runs independently so it isn't biased by the implementer's own reasoning
- Tools: Read, Grep, Glob, Bash (read-only usage)

## security-reviewer

- Signal: auth, payments, crypto, or other security-sensitive code paths
- Purpose: audits changes for injection, auth bypass, secret leakage, and other OWASP-class issues before merge
- Tools: Read, Grep, Glob

## api-documenter

- Signal: REST/GraphQL API project without generated docs
- Purpose: generates/updates OpenAPI or equivalent schema docs from route definitions
- Tools: Read, Grep, Glob, Write (scoped to docs output)

## performance-analyzer

- Signal: performance-critical service, existing perf regressions, or hot-path code
- Purpose: profiles/analyzes code for bottlenecks and suggests targeted optimizations
- Tools: Read, Grep, Glob, Bash

## ui-reviewer

- Signal: frontend-heavy repo (React/Vue/Angular components)
- Purpose: checks accessibility (a11y), responsive behavior, and visual consistency
- Tools: Read, Grep, Glob, Bash (for running a headless browser check if Playwright MCP is present)

## test-writer

- Signal: low test coverage, or new feature work landing without tests
- Purpose: generates unit/integration tests matching existing project conventions
- Tools: Read, Grep, Glob, Write, Bash (to run the new tests)

## General Guidance

- Restrict subagent tool access to the minimum needed — a reviewer agent shouldn't have Write/Edit.
- Subagents are best for work that benefits from a *fresh, unbiased* context (review) or from running *in parallel* with other work (independent analyses) — not for tasks needing the main conversation's full history.
- Don't recommend a subagent for something a plain skill or hook would handle more simply.
