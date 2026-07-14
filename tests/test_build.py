from moe import render
from moe.knowledge import build_expert_knowledge
from moe.roster import BUILDER_TOOLS, ExpertSpec, MaterialSpec, Roster

MD = b"# Valves\n## Mitral\nThe mitral valve is on the left side of the heart.\n"
PLAYBOOK = b"# Workflow\n## Steps\nScaffold, add materials, then run the build.\n"


def _roster(tmp_path):
    mat = tmp_path / "experts" / "cardiology" / "materials"
    mat.mkdir(parents=True)
    (mat / "valves.md").write_bytes(MD)
    expert = ExpertSpec(
        name="cardiology",
        description="Heart anatomy and valves.",
        materials=[
            MaterialSpec(
                path="experts/cardiology/materials/valves.md", title="Valves Primer"
            )
        ],
    )
    return Roster(name="t", experts=[expert]), expert


def _builder(tmp_path):
    mat = tmp_path / "experts" / "expert-builder" / "materials"
    mat.mkdir(parents=True)
    (mat / "workflow.md").write_bytes(PLAYBOOK)
    return ExpertSpec(
        name="expert-builder",
        kind="builder",
        dev_only=True,
        description="Builds other experts.",
        tools=list(BUILDER_TOOLS),
        materials=[
            MaterialSpec(
                path="experts/expert-builder/materials/workflow.md", title="Build workflow"
            )
        ],
    )


def test_build_knowledge_emits_cited_markdown(tmp_path):
    roster, expert = _roster(tmp_path)
    summary = build_expert_knowledge(expert, tmp_path)
    assert summary["sources"] == 1
    kmd = (tmp_path / "experts/cardiology/knowledge/valves-primer.md").read_text()
    assert "mitral valve is on the left" in kmd.lower()
    assert "source_id:" in kmd  # front-matter carries citation metadata
    index = (tmp_path / "experts/cardiology/knowledge/INDEX.md").read_text()
    assert "valves-primer.md" in index


def test_build_all_produces_all_host_builds(tmp_path):
    roster, _ = _roster(tmp_path)
    build_expert_knowledge(roster.experts[0], tmp_path)
    builds = render.build_all(roster, tmp_path)
    assert set(builds) == {"claude-code", "codex", "agents", "dev"}

    cc = (tmp_path / "dist/claude-code/.claude/agents/moe-cardiology.md").read_text()
    assert "name: moe-cardiology" in cc
    assert "{{MOE_ROOT}}/knowledge/cardiology" in cc  # placeholder resolved by installer

    # generic build inlines expert modes (no subagent primitive)
    generic = (tmp_path / "dist/agents/.agents/skills/moe/SKILL.md").read_text()
    assert "## Experts" in generic
    assert "knowledge/cardiology" in generic

    # knowledge is copied into every build so the skill is self-contained
    assert (tmp_path / "dist/claude-code/.claude/skills/moe/knowledge/cardiology/INDEX.md").exists()
    assert (tmp_path / "dist/codex/.codex/agents/moe-cardiology.toml").exists()


def test_builder_kind_renders_procedural_template(tmp_path):
    _, cardio = _roster(tmp_path)
    builder = _builder(tmp_path)
    roster = Roster(name="t", experts=[cardio, builder])
    for e in roster.experts:
        build_expert_knowledge(e, tmp_path)
    render.build_all(roster, tmp_path)

    # The builder appears only in the dev build, rendered from the procedural template.
    agent = (tmp_path / "dist/dev/.claude/agents/moe-expert-builder.md").read_text()
    assert "procedural expert that builds" in agent  # builder-behavior.md, not the citation one
    assert "Two modes" in agent
    assert "WebSearch" in agent  # elevated tools in front-matter
    assert "only source you" not in agent  # the knowledge-expert template's phrasing


def test_dev_only_expert_excluded_from_shipped_builds(tmp_path):
    _, cardio = _roster(tmp_path)
    builder = _builder(tmp_path)
    roster = Roster(name="t", experts=[cardio, builder])
    for e in roster.experts:
        build_expert_knowledge(e, tmp_path)
    render.build_all(roster, tmp_path)

    # Present in dev, absent from every shipped build.
    assert (tmp_path / "dist/dev/.claude/agents/moe-expert-builder.md").exists()
    assert not (tmp_path / "dist/claude-code/.claude/agents/moe-expert-builder.md").exists()
    assert not (tmp_path / "dist/codex/.codex/agents/moe-expert-builder.toml").exists()

    # Absent from the shipped router roster, present in the dev router roster.
    shipped_skill = (tmp_path / "dist/claude-code/.claude/skills/moe/SKILL.md").read_text()
    dev_skill = (tmp_path / "dist/dev/.claude/skills/moe/SKILL.md").read_text()
    assert "expert-builder" not in shipped_skill
    assert "moe-expert-builder" in dev_skill
