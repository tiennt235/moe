from moe import render
from moe.knowledge import build_expert_knowledge
from moe.roster import ExpertSpec, MaterialSpec, Roster

MD = b"# Valves\n## Mitral\nThe mitral valve is on the left side of the heart.\n"


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


def test_build_knowledge_emits_cited_markdown(tmp_path):
    roster, expert = _roster(tmp_path)
    summary = build_expert_knowledge(expert, tmp_path)
    assert summary["sources"] == 1
    kmd = (tmp_path / "experts/cardiology/knowledge/valves_primer.md").read_text()
    assert "mitral valve is on the left" in kmd.lower()
    assert "source_id:" in kmd  # front-matter carries citation metadata
    index = (tmp_path / "experts/cardiology/knowledge/INDEX.md").read_text()
    assert "valves_primer.md" in index


def test_build_all_produces_three_host_builds(tmp_path):
    roster, _ = _roster(tmp_path)
    build_expert_knowledge(roster.experts[0], tmp_path)
    builds = render.build_all(roster, tmp_path)
    assert set(builds) == {"claude-code", "codex", "agents"}

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
