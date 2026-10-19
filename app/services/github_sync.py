"""Safe GitHub synchronization for projects stored in the local save folder.

Git owns authentication through the user's configured credential helper. The
application never stores a GitHub password or token and never force-resets a
working tree. Pulls are fast-forward-only and automatic commits stage only the
saved ELS file.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse


class GitHubSyncError(RuntimeError):
    """Short, safe-to-display GitHub synchronization error."""


def validate_github_remote(value: str) -> str:
    value = str(value or "").strip()
    if not value or any(ord(char) < 32 for char in value):
        raise GitHubSyncError("Enter a GitHub HTTPS or SSH repository URL.")
    parsed = urlparse(value)
    valid_https = (parsed.scheme == "https" and parsed.hostname == "github.com"
                   and not parsed.username and not parsed.password and not parsed.query
                   and not parsed.fragment and bool(re.fullmatch(r"/[^/\s]+/[^/\s]+/?", parsed.path)))
    valid_ssh = (parsed.scheme == "ssh" and parsed.hostname == "github.com"
                 and parsed.username == "git" and not parsed.password and not parsed.query
                 and not parsed.fragment and bool(re.fullmatch(r"/[^/\s]+/[^/\s]+/?", parsed.path)))
    valid_scp = bool(re.fullmatch(r"git@github\.com:[^/:\s]+/[^/:\s]+", value, re.IGNORECASE))
    if not (valid_https or valid_ssh or valid_scp):
        raise GitHubSyncError("Use a GitHub URL such as https://github.com/user/repo.git or git@github.com:user/repo.git.")
    return value


def validate_branch(value: str) -> str:
    value = str(value or "").strip()
    if (not re.fullmatch(r"[A-Za-z0-9._/-]{1,120}", value)
            or value.startswith(("-", "/")) or value.endswith(("/", "."))
            or ".." in value or "//" in value or "@{" in value):
        raise GitHubSyncError("Enter a valid Git branch name, for example main.")
    return value


def _normalized_remote(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^git@github\.com:", "https://github.com/", value, flags=re.IGNORECASE)
    value = re.sub(r"^ssh://git@github\.com/", "https://github.com/", value, flags=re.IGNORECASE)
    value = value.removesuffix(".git").rstrip("/")
    return value.casefold()


class GitHubSync:
    def __init__(self, local_folder: str | Path, remote_url: str, branch: str = "main",
                 *, noninteractive: bool = False):
        self.local_folder = Path(local_folder).expanduser()
        self.remote_url = validate_github_remote(remote_url)
        self.branch = validate_branch(branch)
        self.noninteractive = bool(noninteractive)

    def _run(self, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        if self.noninteractive:
            env["GCM_INTERACTIVE"] = "never"
        try:
            result = subprocess.run(
                ["git", "-C", str(self.local_folder), *args],
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=45, env=env,
                check=False,
            )
        except FileNotFoundError:
            raise GitHubSyncError("Git is not installed. Install Git for Windows and try again.") from None
        except subprocess.TimeoutExpired:
            raise GitHubSyncError("GitHub did not respond in time. The local project files were left unchanged.") from None
        except OSError:
            raise GitHubSyncError("Could not start Git. Check the Git installation and local save folder.") from None
        if check and result.returncode:
            self._raise_safe_error(result.stderr or result.stdout)
        return result

    @staticmethod
    def _raise_safe_error(detail: str) -> None:
        detail = (detail or "").casefold()
        if "not a git repository" in detail or "no such file or directory" in detail:
            message = "The local save folder is not a Git clone. Clone the GitHub repository there first."
        elif any(part in detail for part in ("authentication failed", "could not read username",
                                             "permission denied (publickey)", "terminal prompts disabled")):
            message = "GitHub sign-in failed. Sign in with Git Credential Manager or GitHub Desktop, then retry."
        elif any(part in detail for part in ("repository not found", "requested url returned error: 403",
                                             "requested url returned error: 404", "could not resolve host")):
            message = "GitHub repository is unavailable or this account has no access. Check the URL and permissions."
        elif any(part in detail for part in ("not possible to fast-forward", "non-fast-forward",
                                             "would be overwritten", "divergent branches")):
            message = "GitHub changes cannot be applied as a fast-forward. Nothing was reset; resolve the local/remote divergence first."
        elif any(part in detail for part in ("please tell me who you are", "unable to auto-detect email")):
            message = "Git commit identity is missing. Set user.name and user.email in Git, then save again."
        elif "couldn't find remote ref" in detail or "remote ref does not exist" in detail:
            message = "The configured branch does not exist on GitHub. Check the branch name."
        else:
            message = "GitHub operation failed. Check the repository, branch, Git status and account permissions."
        raise GitHubSyncError(message)

    def _repository_root(self) -> Path:
        if not self.local_folder.is_dir():
            raise GitHubSyncError("The local project folder does not exist. Set it in General settings first.")
        result = self._run(["rev-parse", "--show-toplevel"], check=False)
        if result.returncode:
            self._raise_safe_error(result.stderr or result.stdout)
        try:
            return Path(result.stdout.strip()).resolve()
        except (OSError, ValueError):
            raise GitHubSyncError("Git returned an invalid local repository path.") from None

    def _ensure_origin_and_branch(self) -> Path:
        root = self._repository_root()
        current = self._run(["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
        branch = current.stdout.strip()
        if current.returncode or not branch:
            raise GitHubSyncError("The local repository has no active branch. Check it out in GitHub Desktop first.")
        if branch != self.branch:
            raise GitHubSyncError(f"The local branch is '{branch}', but Settings specifies '{self.branch}'. Select the matching branch.")
        remote = self._run(["remote", "get-url", "origin"], check=False)
        if remote.returncode:
            self._run(["remote", "add", "origin", self.remote_url])
        elif _normalized_remote(remote.stdout) != _normalized_remote(self.remote_url):
            raise GitHubSyncError("The local repository's origin URL differs from Settings. Verify it in GitHub Desktop; it was not changed.")
        return root

    def pull(self) -> str:
        self._ensure_origin_and_branch()
        self._run(["fetch", "--no-tags", "origin", self.branch])
        result = self._run(["merge", "--ff-only", "FETCH_HEAD"])
        return result.stdout.strip() or "Already up to date."

    def push(self) -> str:
        self._ensure_origin_and_branch()
        result = self._run(["push", "origin", self.branch])
        return result.stderr.strip() or result.stdout.strip() or "Push completed."

    def commit_file(self, file_path: str | Path, project_name: str) -> str:
        root = self._ensure_origin_and_branch()
        path = Path(file_path).expanduser().resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            return "outside-repository"
        if path.suffix.casefold() != ".els" or not path.is_file():
            return "not-project-file"
        title = re.sub(r"[\r\n\x00-\x1f]+", " ", path.name).strip()
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
        message = f"{title} — {timestamp}"
        # Stage the saved path first so both new and already-tracked projects
        # are included. --only then commits this path's current worktree
        # contents without sweeping unrelated staged files into the commit.
        self._run(["add", "--", relative])
        self._run(["commit", "--only", "--allow-empty", "-m", message, "--", relative])
        # Never report a successful save-commit if Git left this path modified
        # (for example, because of a hook or a path/index mismatch).
        remaining = self._run(["diff", "--quiet", "HEAD", "--", relative], check=False)
        if remaining.returncode != 0:
            raise GitHubSyncError("Git did not include the saved project file in its commit. Check the repository and try saving again.")
        return "committed"
