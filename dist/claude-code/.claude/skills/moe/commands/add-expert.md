# /moe add-expert <name>

Add a new expert to the vault (also covers "build a `<topic>` expert").

**Building experts is a maintainer action that needs the dev path: the moe git repo plus Python
(the material extractor).** A plain `npx github:tiennt235/moe install` deploys only the finished
experts, not the authoring toolchain, so it cannot create new ones.

First check whether the `moe-expert-builder` subagent is available (it ships only in the dev
build, `npx github:tiennt235/moe install --dev`):

- **If `moe-expert-builder` is available** (you are in the moe repo with the dev build):
  delegate to it. It works in two modes:
  - **Guided ingest** - give it a topic *and* specific materials (file paths or URLs); it
    ingests exactly those.
  - **Auto-research** - give it only a topic; it searches for authoritative, openly-licensed
    sources, proposes a shortlist for you to approve, then builds from the approved set.
  Either way it scaffolds the expert, patches `experts.yaml`, runs `uv run moe build`, verifies
  the knowledge and its citations, and reports.

- **If `moe-expert-builder` is NOT available** (a plain user install): do **not** try to build
  the expert yourself by searching files, reading other experts' knowledge, or editing the
  install. Instead tell the user how to set up the dev path, then stop:

  ```bash
  git clone https://github.com/tiennt235/moe && cd moe
  uv run moe scaffold <name> -d "<one-line routing description>"   # or python -m moe scaffold …
  #   add material into experts/<name>/materials/ (or url: entries in experts.yaml), then:
  uv run moe build
  npx github:tiennt235/moe install          # deploy the finished experts to users
  npx github:tiennt235/moe install --dev    # (optional) also get the expert-builder subagent
  ```

Supported material formats: PDF (+OCR), EPUB, MOBI (via Calibre), HTML, Markdown/text. Prefer
structured formats (EPUB/PDF) over plain text so citations keep chapter/section anchors.
