# moe — mixture of domain experts

Route a domain question to the right expert(s) on the team and return a **cited** answer.
The team and what each expert knows:

{{ROSTER}}

## When to use
Use this for substantive questions that one of the experts above covers. For anything outside
the team's domains, answer normally — do not force-fit an expert.

## How to answer — `/moe ask "<question>"`
1. **Select** the expert(s) whose description best matches the question. More than one may
   apply; pick every one that clearly does (usually 1–2). If none fit, say so and stop.
2. **Delegate** to each selected expert:
{{DELEGATION}}
3. **Synthesize** one answer from what the expert(s) return. Preserve every citation
   (`source · section · page`). If experts disagree, surface both sides with their citations.
4. If the knowledge base does not contain the answer, say so plainly — never invent.

## Commands
- `/moe ask "<q>"` — route → answer (this is the default).
- `/moe route "<q>"` — show which expert(s) you would pick and why; do **not** answer.
- `/moe list` — list the team and what each expert knows.
- `/moe add-expert <name>` — scaffold a new expert.
- `/moe build` — rebuild knowledge + per-host outputs.

Every expert answers **only** from its own knowledge folder and cites it. Routing is your
judgment over the descriptions above — there is no vector search and no embeddings.
