# Skills Reference

Skills package repeatable expertise/workflows into `.claude/skills/<name>/SKILL.md`. A skill can bundle
templates, scripts, and reference docs alongside the markdown instructions.

## Frontmatter Options

```yaml
---
name: skill-name
description: What it does and when to use it (this is what Claude matches against)
tools: Read, Grep, Bash        # optional: restrict tool access
disable-model-invocation: true # optional: user-only, invoked via /skill-name
user-invocable: false          # optional: Claude-only, background knowledge
---
```

- **Both** (default, omit both flags): Claude can invoke automatically when relevant, user can also run `/skill-name`.
- **User-only** (`disable-model-invocation: true`): for anything with side effects — deploys, commits, sending messages. Prevents Claude from triggering it unprompted.
- **Claude-only** (`user-invocable: false`): background knowledge/conventions the user never needs to invoke directly.

## Common Off-the-Shelf Skills (via plugins)

| Skill | Plugin | When relevant |
|-------|--------|----------------|
| skill-development | plugin-dev | Repo is itself building Claude Code plugins/skills |
| commit | commit-commands | Team wants a consistent commit-message workflow |
| frontend-design | frontend-design | React/Vue/Angular UI work |
| writing-rules | hookify | Team wants to codify hook-writing conventions |
| feature-dev | feature-dev | Repo does structured feature planning before implementation |

## Custom Skills Worth Creating

| Signal | Skill | Invocation | Notes |
|--------|-------|------------|-------|
| REST/GraphQL API routes | `api-doc` | Both | Bundle an OpenAPI/schema template |
| DB migrations directory | `create-migration` | User-only | Bundle a validation script |
| Existing test suite | `gen-test` | User-only | Bundle example test files matching project conventions |
| Component library | `new-component` | User-only | Bundle boilerplate templates |
| PR workflow / CONTRIBUTING.md | `pr-check` | User-only | Bundle a review checklist |
| Tagged releases / CHANGELOG | `release-notes` | User-only | Pull git log context automatically |
| Non-obvious style conventions | `project-conventions` | Claude-only | Encodes tribal knowledge new contributors wouldn't guess |
| Onboarding docs / setup scripts | `setup-dev` | User-only | Bundle a prereq-check script |

## Design Guidance

- Keep the `description` field specific and trigger-oriented — it's the only thing matched against user intent before the skill body is read.
- Bundle scripts/templates as files next to SKILL.md rather than inlining large code blocks.
- Prefer one skill per distinct workflow over one mega-skill with branching logic.
