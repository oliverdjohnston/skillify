"""The project's own skills must parse under strict YAML, or `npx skills add` skips them."""

from pathlib import Path

SKILLS = Path(__file__).parents[2] / "skills"


def test_skill_frontmatter_is_strict_yaml():
    folders = sorted(p.parent for p in SKILLS.glob("*/SKILL.md"))
    assert folders
    for folder in folders:
        head = (folder / "SKILL.md").read_text().split("---")[1]
        fields = dict(line.split(": ", 1) for line in head.strip().splitlines())
        assert fields["name"] == folder.name
        for value in fields.values():
            # an unquoted ": " is a nested mapping to strict parsers
            assert value[0] in "'\"" or ": " not in value, folder.name
