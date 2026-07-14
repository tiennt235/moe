---
title: "Roster schema (experts.yaml)"
origin: "experts/expert-builder/materials/roster-schema.md"
format: markdown
source_id: 1ff4e2515c7ef09d
sections: 3
---

# Roster schema (experts.yaml)
## Roster schema (experts.yaml)

The roster at the repo root drives everything. It is a YAML file with a `name` and a list of
`experts`. Each expert entry has these fields.

## Roster schema (experts.yaml) › Fields

- `name` (required): the expert's display name. Its slug (kebab-case, lowercase) becomes the
  directory `experts/<slug>/` and the agent name `moe-<slug>`.
- `description` (required): one or two sentences saying what the expert knows and when to route
  to it. **This is the only routing signal** — the host model matches a question against these
  descriptions. Write it concretely; name the sub-topics and end with a "Route here for …" cue.
- `kind` (optional, default `knowledge`): either `knowledge` (answers from its corpus and cites
  it) or `builder` (a procedural meta-expert that creates other experts). New domain experts
  are always `knowledge`.
- `dev_only` (optional, default `false`): when `true`, the expert is excluded from the shipped
  end-user builds and the router roster; it ships only in the `dist/dev` build. Reserve this for
  tools that need the repo + Python to run (the expert-builder itself). Domain experts are not
  `dev_only`.
- `materials` (optional): the list of sources (see the formats reference). Each is a mapping
  with `path:` (repo-relative file) or `url:`, plus optional `title:` and `author:`.
- `tools` (optional, default `[Read, Grep, Glob]`): the tools the subagent may use. Knowledge
  experts stay read-only.
- `model` (optional): a Claude Code model hint for the subagent.
- `proactive` (optional, default `true`): when true the subagent's description invites
  proactive auto-routing.

## Roster schema (experts.yaml) › Example entry

```yaml
  - name: cardiology
    description: >-
      Clinical cardiology — cardiac anatomy, the heart's chambers and valves, valvular disease
      (stenosis and regurgitation), and blood flow. Route here for heart questions.
    materials:
      - path: experts/cardiology/materials/valves.md
        title: Cardiac Valves Primer
    tools: [Read, Grep, Glob]
```
