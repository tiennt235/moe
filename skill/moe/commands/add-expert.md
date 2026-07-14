# /moe add-expert &lt;name&gt;

Scaffold a new expert: create `experts/&lt;name&gt;/` with a starter `EXPERT.md` and an empty
`materials/` folder, and add a roster entry to `experts.yaml`. Then drop source material
(PDF/EPUB/HTML/Markdown) into `materials/`, write a good one-line `description` (it drives
routing), and run `/moe build`.

Authoring/dev path (needs Python): `uv run moe scaffold &lt;name&gt;` (or `python -m moe scaffold
&lt;name&gt;`), then `uv run moe build`.
