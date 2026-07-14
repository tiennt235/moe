---
name: moe
description: Route a domain question to the right expert(s) and answer with citations. Use for questions about: cardiology, nutrition, stoicism.
---

# moe — mixture of domain experts

Route a domain question to the right expert(s) on the team and return a **cited** answer.
The team and what each expert knows:

- **cardiology** (`moe-cardiology`) — Clinical cardiology — cardiac anatomy, the heart's chambers and valves, valvular disease (stenosis and regurgitation), and blood flow through the heart. Route here for heart / cardiovascular questions.
- **nutrition** (`moe-nutrition`) — Human nutrition — macronutrients, dietary fats and cholesterol, sodium and blood pressure, and heart-healthy eating patterns (Mediterranean, DASH). Route here for diet, food, and nutrition questions.
- **stoicism** (`moe-stoicism`) — Stoic philosophy from the primary sources — Marcus Aurelius's Meditations and Epictetus's Enchiridion: the dichotomy of control (what is up to us), living according to nature and reason, virtue as the sole good, and practical self-discipline. Route here for Stoicism, Stoic ethics, and questions about Marcus Aurelius or Epictetus.

## When to use
Use this for substantive questions that one of the experts above covers. For anything outside
the team's domains, answer normally — do not force-fit an expert.

## How to answer — `/moe ask "<question>"`
1. **Select** the expert(s) whose description best matches the question. More than one may
   apply; pick every one that clearly does (usually 1–2). If none fit, say so and stop.
2. **Delegate** to each selected expert:
   - Spawn the expert's subagent via the Agent/Task tool with `subagent_type: "moe-<name>"`, passing the question. Run several in parallel when
     more than one expert applies; each subagent searches its own knowledge and returns cited findings.
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
