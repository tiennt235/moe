# /moe add-expert &lt;name&gt;

Scaffold a new expert: create `experts/&lt;name&gt;/` with a starter `EXPERT.md` and an empty
`materials/` folder, and add a roster entry to `experts.yaml`. Then drop source material
(PDF/EPUB/HTML/Markdown) into `materials/`, write a good one-line `description` (it drives
routing), and run `/moe build`.

Equivalent CLI: `npx moe scaffold &lt;name&gt;`.
