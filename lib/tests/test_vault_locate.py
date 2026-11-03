"""Tests for lib/vault_locate.py. Run: python -m unittest discover lib/tests"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vault_locate as vl  # noqa: E402

ENV_KEY = "CLAUDE_PLUGIN_OPTION_VAULT_PATH"


def write(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def hub(name, repo_line, remote_line=None):
    lines = ["---", "type: project", "---", f"# {name}", "", "**Goal.** Something.", "", repo_line]
    if remote_line:
        lines.append(remote_line)
    return "\n".join(lines) + "\n"


class VaultLocateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.vault = os.path.join(self.root, "vault")
        write(os.path.join(self.vault, "CLAUDE.md"), "# Vault Schema & Rules (template v0.7)\n")
        os.makedirs(os.path.join(self.vault, "raw"))
        write(os.path.join(self.vault, "index.md"), "# Index\n")
        self.proj = os.path.join(self.root, "code", "proj1")
        os.makedirs(os.path.join(self.proj, "src"))

    def tearDown(self):
        self.tmp.cleanup()

    def add_hub(self, name, repo_line, remote_line=None):
        write(os.path.join(self.vault, "projects", name, f"{name}.md"), hub(name, repo_line, remote_line))

    def git_config(self, folder, url):
        write(os.path.join(folder, ".git", "config"),
              f'[core]\n\tbare = false\n[remote "origin"]\n\turl = {url}\n\tfetch = +refs/heads/*\n')

    # --- vault detection ------------------------------------------------------------------

    def test_is_vault_needs_marker_and_raw(self):
        self.assertTrue(vl.is_vault(self.vault))
        other = os.path.join(self.root, "notvault")
        write(os.path.join(other, "CLAUDE.md"), "# Project rules\n")
        os.makedirs(os.path.join(other, "raw"))
        self.assertFalse(vl.is_vault(other))
        noraw = os.path.join(self.root, "noraw")
        write(os.path.join(noraw, "CLAUDE.md"), "# Vault Schema & Rules\n")
        self.assertFalse(vl.is_vault(noraw))

    def test_find_vaults_from_inside(self):
        inner = os.path.join(self.vault, "wiki", "concepts")
        os.makedirs(inner)
        self.assertEqual([vl.norm(v) for v in vl.find_vaults(inner)], [vl.norm(self.vault)])
        self.assertEqual(vl.find_vaults(self.proj), [])

    def test_configured_vault_reads_env(self):
        self.assertEqual(vl.norm(vl.configured_vault({ENV_KEY: self.vault})), vl.norm(self.vault))
        self.assertIsNone(vl.configured_vault({}))
        self.assertIsNone(vl.configured_vault({ENV_KEY: ""}))
        self.assertIsNone(vl.configured_vault({ENV_KEY: "   "}))
        self.assertIsNone(vl.configured_vault({ENV_KEY: self.proj}))  # not a vault
        self.assertIsNone(vl.configured_vault({ENV_KEY: os.path.join(self.root, "missing")}))

    def test_configured_vault_accepts_forward_slashes_and_quotes(self):
        fwd = self.vault.replace("\\", "/")
        self.assertEqual(vl.norm(vl.configured_vault({ENV_KEY: fwd})), vl.norm(self.vault))
        self.assertEqual(vl.norm(vl.configured_vault({ENV_KEY: f'"{self.vault}"'})), vl.norm(self.vault))

    def test_locate_prefers_enclosing_vault(self):
        other = os.path.join(self.root, "vault2")
        write(os.path.join(other, "CLAUDE.md"), "# Vault Schema & Rules\n")
        os.makedirs(os.path.join(other, "raw"))
        env = {ENV_KEY: self.vault}
        self.assertEqual(vl.norm(vl.locate(other, env)), vl.norm(other))
        self.assertEqual(vl.norm(vl.locate(self.proj, env)), vl.norm(self.vault))
        self.assertIsNone(vl.locate(self.proj, {}))

    # --- remotes --------------------------------------------------------------------------

    def test_normalize_remote_forms(self):
        want = "github.com/owner/repo"
        for url in ("https://github.com/owner/repo.git", "https://github.com/Owner/Repo",
                    "git@github.com:owner/repo.git", "ssh://git@github.com/owner/repo",
                    "ssh://git@github.com:22/owner/repo.git", "https://user@github.com/owner/repo/",
                    "github.com/owner/repo", "  github.com/owner/repo.git  "):
            self.assertEqual(vl.normalize_remote(url), want, url)

    def test_git_remotes_from_subfolder(self):
        self.git_config(self.proj, "git@github.com:me/proj1.git")
        self.assertEqual(vl.git_remotes(os.path.join(self.proj, "src")), ["github.com/me/proj1"])

    def test_git_remotes_worktree_file(self):
        self.git_config(self.proj, "https://github.com/me/proj1")
        gitdir = os.path.join(self.proj, ".git", "worktrees", "wt")
        write(os.path.join(gitdir, "commondir"), "../..\n")
        wt = os.path.join(self.root, "wt")
        write(os.path.join(wt, ".git"), f"gitdir: {gitdir}\n")
        self.assertEqual(vl.git_remotes(wt), ["github.com/me/proj1"])

    def test_git_remotes_none(self):
        self.assertEqual(vl.git_remotes(self.proj), [])

    # --- hubs -----------------------------------------------------------------------------

    def test_read_hub_path_and_remote(self):
        self.add_hub("proj1", f"**Repo.** `{self.proj}` (public). Last seen commit: `abc1234`",
                     "**Remote.** `github.com/me/proj1`")
        info = vl.read_hub(os.path.join(self.vault, "projects", "proj1", "proj1.md"))
        self.assertEqual(vl.norm(info["repo"]), vl.norm(self.proj))
        self.assertEqual(info["remote"], "github.com/me/proj1")

    def test_read_hub_url_repo_is_remote(self):
        self.add_hub("web", "**Repo.** `https://github.com/me/web.git`. Last seen commit: none")
        info = vl.read_hub(os.path.join(self.vault, "projects", "web", "web.md"))
        self.assertIsNone(info["repo"])
        self.assertEqual(info["remote"], "github.com/me/web")

    def test_read_hub_none_repo(self):
        self.add_hub("idea", "**Repo.** none. Last seen commit: none")
        info = vl.read_hub(os.path.join(self.vault, "projects", "idea", "idea.md"))
        self.assertIsNone(info["repo"])
        self.assertIsNone(info["remote"])

    def test_list_hubs_skips_non_hub_files(self):
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        write(os.path.join(self.vault, "projects", "proj1", "proj1-history.md"), "# history\n")
        write(os.path.join(self.vault, "projects", "proj1", "notes.md"), "# notes\n")
        self.assertEqual([name for name, _ in vl.list_hubs(self.vault)], ["proj1"])

    def test_match_by_path_and_subfolder(self):
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        self.add_hub("other", f"**Repo.** `{os.path.join(self.root, 'code', 'other')}`")
        for cwd in (self.proj, os.path.join(self.proj, "src")):
            self.assertEqual([m["name"] for m in vl.match_hubs(cwd, self.vault)], ["proj1"], cwd)

    def test_match_path_with_forward_slashes(self):
        self.add_hub("proj1", f"**Repo.** `{self.proj.replace(os.sep, '/')}`")
        self.assertEqual([m["name"] for m in vl.match_hubs(self.proj, self.vault)], ["proj1"])

    def test_sibling_prefix_does_not_match(self):
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        sibling = self.proj + "-old"
        os.makedirs(sibling)
        self.assertEqual(vl.match_hubs(sibling, self.vault), [])

    def test_parent_folder_does_not_match(self):
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        self.assertEqual(vl.match_hubs(os.path.join(self.root, "code"), self.vault), [])

    def test_deepest_path_wins(self):
        sub = os.path.join(self.proj, "packages", "api")
        os.makedirs(sub)
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        self.add_hub("api", f"**Repo.** `{sub}`")
        self.assertEqual([m["name"] for m in vl.match_hubs(sub, self.vault)], ["api"])

    def test_two_hubs_same_path_both_returned(self):
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        self.add_hub("proj1-v2", f"**Repo.** `{self.proj}`")
        self.assertEqual(sorted(m["name"] for m in vl.match_hubs(self.proj, self.vault)),
                         ["proj1", "proj1-v2"])

    def test_match_by_remote_when_path_differs(self):
        clone = os.path.join(self.root, "elsewhere", "proj1")
        os.makedirs(clone)
        self.git_config(clone, "https://github.com/me/proj1.git")
        self.add_hub("proj1", f"**Repo.** `{self.proj}`", "**Remote.** github.com/me/proj1")
        matches = vl.match_hubs(clone, self.vault)
        self.assertEqual([(m["name"], m["by"]) for m in matches], [("proj1", "remote")])

    def test_path_match_beats_remote_match(self):
        self.git_config(self.proj, "https://github.com/me/shared")
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        self.add_hub("fork", "**Repo.** `https://github.com/me/shared`")
        self.assertEqual([m["name"] for m in vl.match_hubs(self.proj, self.vault)], ["proj1"])

    def test_undecodable_hub_is_skipped(self):  # regression: spec-only test SS-56/57
        path = os.path.join(self.vault, "projects", "bad", "bad.md")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(f"**Repo.** `{self.proj}`\n".encode("ascii") + b"\x80\x81\xff\n")
        self.add_hub("proj1", f"**Repo.** `{self.proj}`")
        self.assertEqual([m["name"] for m in vl.match_hubs(self.proj, self.vault)], ["proj1"])

    def test_no_projects_folder(self):
        self.assertEqual(vl.match_hubs(self.proj, self.vault), [])


if __name__ == "__main__":
    unittest.main()
