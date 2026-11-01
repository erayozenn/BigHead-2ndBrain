"""Skills must not pre-approve git commands whose --output option writes a file."""

import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"
WRITING_COMMANDS = re.compile(r"^\s*-\s*Bash\(git\b.*\b(log|rev-list)\b", re.MULTILINE)


class SkillPermissionsTest(unittest.TestCase):
    def test_no_preapproved_git_command_can_write_a_file(self):
        skills = sorted(SKILLS.glob("*/SKILL.md"))
        self.assertTrue(skills)
        for skill in skills:
            frontmatter = skill.read_text(encoding="utf-8").split("\n---", 1)[0]
            self.assertIsNone(WRITING_COMMANDS.search(frontmatter), skill.parent.name)

    def test_no_wildcard_before_a_git_subcommand(self):
        # `git -C * status *` also matches `git -C . -c core.fsmonitor=<cmd> status`.
        for skill in sorted(SKILLS.glob("*/SKILL.md")):
            frontmatter = skill.read_text(encoding="utf-8").split("\n---", 1)[0]
            self.assertIsNone(re.search(r"^\s*-\s*Bash\(git\s+[-*]", frontmatter, re.MULTILINE),
                              skill.parent.name)


if __name__ == "__main__":
    unittest.main()
