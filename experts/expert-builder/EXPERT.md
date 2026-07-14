# Additional guidance — expert-builder

- Operate **only** inside the moe repo via the Python dev path. Every mutation goes through
  `uv run moe scaffold` / `uv run moe build` and edits to `experts.yaml` — never hand-write
  files under `experts/<slug>/knowledge/`, they are generated.
- **Slugs** are kebab-case and lowercase (`slugify` handles this); the agent name is
  `moe-<slug>`. Keep names short and unambiguous, one domain each.
- **Descriptions drive routing.** Write the `description` to say what the expert *knows* and
  when to route to it, in one or two sentences (e.g. "Clinical cardiology — anatomy, valves,
  valvular disease … Route here for heart questions."). Vague descriptions cause mis-routing.
- **One domain per expert.** If materials span two clearly separate domains, build two experts.
- **Licensing is a hard gate.** Knowledge is committed to this repo, so only ingest sources
  that permit redistribution (public domain, open licenses, or official/canonical pages you
  are cleared to mirror). When unsure, ask the user rather than ingesting.
- Prefer a small set of high-quality, authoritative sources over many shallow ones.
- After building, always report the deploy step: `npx github:tiennt235/moe install` for end
  users, `npx github:tiennt235/moe install --dev` to pick up builder/dev-only experts.
