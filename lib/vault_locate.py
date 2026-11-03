"""Find the vault and the project hub that belongs to a folder.

Used by the SessionStart hook and skill scripts when a session runs outside the vault.

- A vault is a folder holding raw/ and a CLAUDE.md whose first line starts with VAULT_MARKER
  (the same test as hooks/guard.py).
- The configured vault comes from the plugin option `vault_path`, which Claude Code exports
  to hook processes as CLAUDE_PLUGIN_OPTION_VAULT_PATH.
- A hub is projects/<name>/<name>.md. Its `**Repo.**` line names a local path or a URL in
  backticks; an optional `**Remote.**` line names a remote such as github.com/owner/repo.
- Remotes are read from .git/config as text. No git command runs: a repo's own configuration
  can run commands.

Standard library only; Python 3.10+.
"""

from __future__ import annotations

import os
import re

VAULT_MARKER = "# Vault Schema & Rules"
ENV_KEY = "CLAUDE_PLUGIN_OPTION_VAULT_PATH"
MSYS_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")
REPO_LINE = re.compile(r"^\*\*Repo\.\*\*\s*(.*)$")
REMOTE_LINE = re.compile(r"^\*\*Remote\.\*\*\s*(.*)$")
BACKTICK = re.compile(r"`([^`]+)`")
URL_LIKE = re.compile(r"^(?:[a-z][a-z0-9+.-]*://|[^/\s]+@[^/\s:]+:)", re.IGNORECASE)
HOST_PATH = re.compile(r"^[a-z0-9.-]+\.[a-z]{2,}(?::\d+)?/\S+", re.IGNORECASE)
GIT_URL = re.compile(r"^\s*url\s*=\s*(.+?)\s*$")
MAX_READ = 256 * 1024


def from_msys(path: str) -> str:
    """On Windows, /c/Users/x (Git Bash form) means C:/Users/x."""
    return MSYS_DRIVE.sub(r"\1:", path) if os.name == "nt" else path


def norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(from_msys(path))))


def is_vault(folder: str) -> bool:
    if not os.path.isdir(os.path.join(folder, "raw")):
        return False
    try:
        with open(os.path.join(folder, "CLAUDE.md"), encoding="utf-8-sig", errors="replace") as f:
            return f.readline().strip().startswith(VAULT_MARKER)
    except OSError:
        return False


def find_vaults(path: str) -> list[str]:
    """Every vault enclosing path (a folder or a file), nearest first."""
    vaults = []
    folder = norm(path)
    if not os.path.isdir(folder):
        folder = os.path.dirname(folder)
    while True:
        if is_vault(folder):
            vaults.append(folder)
        parent = os.path.dirname(folder)
        if parent == folder:
            return vaults
        folder = parent


def configured_vault(env: dict | None = None) -> str | None:
    """The vault named by the plugin option, if that folder is a vault."""
    value = (os.environ if env is None else env).get(ENV_KEY, "")
    value = value.strip().strip('"').strip("'").strip()
    if not value:
        return None
    path = os.path.realpath(os.path.abspath(from_msys(value)))  # keep case for display
    return path if is_vault(path) else None


def locate(cwd: str, env: dict | None = None) -> str | None:
    """The vault enclosing cwd, else the configured vault, else None."""
    enclosing = find_vaults(cwd)
    return enclosing[0] if enclosing else configured_vault(env)


def inside(path: str, folder: str) -> bool:
    """True if path is folder or below it (both normalised)."""
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def normalize_remote(url: str) -> str:
    """github.com/owner/repo for https, ssh and scp-like forms; lower case, no .git."""
    text = url.strip().lower()
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = re.sub(r"^[^/@\s]+@", "", text)
    text = re.sub(r"^([^/:]+):(\d+)/", r"\1/", text)  # host:port/path
    text = re.sub(r"^([^/:]+):", r"\1/", text)  # scp-like host:path
    text = text.rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    return text.rstrip("/")


def _read_text(path: str) -> str:
    with open(path, "rb") as f:
        return f.read(MAX_READ).decode("utf-8", errors="replace")


def _git_dir(start: str) -> str | None:
    folder = norm(start)
    while True:
        dotgit = os.path.join(folder, ".git")
        if os.path.isdir(dotgit):
            return dotgit
        if os.path.isfile(dotgit):
            for line in _read_text(dotgit).splitlines():
                if line.startswith("gitdir:"):
                    target = line[len("gitdir:"):].strip()
                    return target if os.path.isabs(target) else os.path.join(folder, target)
            return None
        parent = os.path.dirname(folder)
        if parent == folder:
            return None
        folder = parent


def git_remotes(start: str) -> list[str]:
    """Normalised remote URLs of the repo enclosing start, read from its config file."""
    try:
        gitdir = _git_dir(start)
        if not gitdir:
            return []
        config = os.path.join(gitdir, "config")
        common = os.path.join(gitdir, "commondir")
        if os.path.isfile(common):
            target = _read_text(common).strip()
            base = target if os.path.isabs(target) else os.path.join(gitdir, target)
            config = os.path.join(base, "config")
        if not os.path.isfile(config):
            return []
        remotes, in_remote = [], False
        for line in _read_text(config).splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_remote = stripped.lower().startswith("[remote ")
                continue
            match = GIT_URL.match(line)
            if in_remote and match:
                remote = normalize_remote(match.group(1).strip('"'))
                if remote and remote not in remotes:
                    remotes.append(remote)
        return remotes
    except OSError:
        return []


def _first_value(rest: str) -> str | None:
    found = BACKTICK.search(rest)
    if found:
        return found.group(1).strip()
    word = rest.strip().split()
    return word[0].rstrip(".,;)") if word else None


def read_hub(path: str) -> dict:
    """{'repo': local path or None, 'remote': normalised remote or None}.

    Raises ValueError for a file that is not valid UTF-8, so a damaged hub is skipped
    instead of being half-read.
    """
    repo = remote = None
    with open(path, "rb") as f:
        text = f.read(MAX_READ).decode("utf-8-sig")  # strict: UnicodeDecodeError is a ValueError
    for line in text.splitlines():
        stripped = line.strip()
        repo_match = REPO_LINE.match(stripped)
        remote_match = REMOTE_LINE.match(stripped)
        if repo_match and repo is None and remote is None:
            value = _first_value(repo_match.group(1))
            if value and value.lower().rstrip(".") != "none":
                if URL_LIKE.match(value) or HOST_PATH.match(value):
                    remote = normalize_remote(value)
                else:
                    repo = from_msys(value)
        elif remote_match:
            value = _first_value(remote_match.group(1))
            if value and value.lower().rstrip(".") != "none":
                remote = normalize_remote(value)
    return {"repo": repo, "remote": remote}


def list_hubs(vault: str) -> list[tuple[str, str]]:
    """(name, path) of every hub: projects/<name>/<name>.md, sorted by name."""
    projects = os.path.join(vault, "projects")
    hubs = []
    try:
        names = sorted(os.listdir(projects))
    except OSError:
        return []
    for name in names:
        path = os.path.join(projects, name, f"{name}.md")
        if os.path.isfile(path):
            hubs.append((name, path))
    return hubs


def match_hubs(cwd: str, vault: str) -> list[dict]:
    """Hubs whose repo is cwd or encloses it (deepest only), else hubs matching a remote."""
    here = norm(cwd)
    by_path, by_remote = [], []
    remotes = None
    for name, path in list_hubs(vault):
        try:
            info = read_hub(path)
        except (OSError, ValueError):
            continue
        if info["repo"]:
            repo = norm(info["repo"])
            if inside(here, repo):
                by_path.append({"name": name, "path": path, "by": "path", "depth": len(repo)})
                continue
        if info["remote"]:
            if remotes is None:
                remotes = git_remotes(cwd)
            if info["remote"] in remotes:
                by_remote.append({"name": name, "path": path, "by": "remote", "depth": 0})
    if by_path:
        deepest = max(m["depth"] for m in by_path)
        return [m for m in by_path if m["depth"] == deepest]
    return by_remote
