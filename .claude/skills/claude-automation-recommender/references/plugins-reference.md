# Plugins Reference

Plugins bundle multiple skills (and sometimes agents/hooks) for one-step install, useful when a team wants
standardized tooling rather than hand-rolled per-repo skills.

## General Productivity

**anthropic-agent-skills**
- Signal: general-purpose recommendation with no strong specialization
- Contains: core document/workflow skills (docx, xlsx, pptx, pdf generation and editing)

## Document Workflows

**docx / xlsx / pdf skills**
- Signal: repo or team regularly produces reports, spreadsheets, or PDFs as deliverables
- Value: structured generation/editing of office documents without hand-rolled scripts

## Frontend Development

**frontend-design**
- Signal: React/Vue/Angular/Svelte project, design-system or component-heavy UI work
- Value: consistent design guidance and component scaffolding conventions

## Building AI Tools

**mcp-builder**
- Signal: repo is building a custom MCP server, or has an internal API with no existing MCP integration
- Value: scaffolding and conventions for building a compliant MCP server from scratch

## Plugin Development

**plugin-dev**
- Signal: repo's purpose is building Claude Code plugins/skills (like this one)
- Value: includes the skill-development skill and conventions for packaging plugins

## Automation Rules

**hookify**
- Signal: team wants to formalize hook-writing conventions across repos
- Value: includes the writing-rules skill for consistent hook authoring

## General Guidance

- Recommend a plugin over a one-off custom skill when the need is generic enough that it's likely already solved (document generation, frontend design conventions) — building custom in that case is wasted effort.
- Recommend a custom skill instead when the workflow is specific to this codebase's conventions or tooling.
- Check `ListPlugins`/marketplace availability before recommending — a great plugin is useless if it isn't accessible to the user's org.
