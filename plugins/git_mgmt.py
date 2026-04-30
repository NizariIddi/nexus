"""
JARVIS Plugin: Git Management
==============================
Full git workflow via natural language.
Covers: init, clone, status, add, commit, push, pull,
        branch, merge, log, diff, stash, tag, remote,
        reset, revert, cherry-pick, blame, and more.

No extra dependencies — just uses the system's git binary.
"""

import os
import subprocess
import shutil
from core.plugin_base import JarvisPlugin


def _run(args: list, cwd: str = None, timeout: int = 60) -> tuple[int, str, str]:
    """Run a git command. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            args,
            capture_output=True, text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd()
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 1, "", "git is not installed. Run: sudo apt install git"
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def _git(*args, cwd=None, timeout=60) -> str:
    """Run git and return formatted output."""
    code, out, err = _run(["git"] + list(args), cwd=cwd, timeout=timeout)
    if code == 0:
        return out or "  ✅ Done."
    return f"  ⚠️  {err or out or 'Git command failed.'}"


def _find_repo(start: str = None) -> str | None:
    """Walk up from start dir to find a .git folder."""
    path = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def _sep(n: int = 50) -> str:
    return "─" * n


class GitPlugin(JarvisPlugin):
    NAME        = "git"
    CATEGORY    = "git"
    DESCRIPTION = "Full Git workflow — commit, push, pull, branch, merge, log, diff & more"

    ACTIONS = [
        # setup
        "git_init", "init",
        "git_clone", "clone",
        "git_config", "config",
        # info
        "git_status", "status",
        "git_log", "log",
        "git_diff", "diff",
        "git_show", "show",
        "git_blame", "blame",
        "git_remote", "remote", "list_remotes",
        "git_tags", "tags", "list_tags",
        "git_branches", "branches", "list_branches",
        "git_stash_list", "stash_list",
        # staging
        "git_add", "add", "stage",
        "git_add_all", "add_all", "stage_all",
        "git_unstage", "unstage", "reset_head",
        "git_discard", "discard", "checkout_file",
        # committing
        "git_commit", "commit",
        "git_amend", "amend",
        # remote sync
        "git_push", "push",
        "git_pull", "pull",
        "git_fetch", "fetch",
        # branching
        "git_branch_create", "create_branch", "new_branch",
        "git_branch_delete", "delete_branch",
        "git_checkout", "checkout", "switch_branch",
        "git_merge", "merge",
        "git_rebase", "rebase",
        "git_cherry_pick", "cherry_pick",
        # stashing
        "git_stash", "stash",
        "git_stash_pop", "stash_pop",
        "git_stash_drop", "stash_drop",
        # undoing
        "git_reset", "reset",
        "git_revert", "revert",
        "git_clean", "clean",
        # tagging
        "git_tag", "tag",
        "git_tag_delete", "delete_tag",
        # remote management
        "git_remote_add", "add_remote",
        "git_remote_remove", "remove_remote",
        # summary
        "git_summary", "summary", "repo_summary",
        "git_contributors", "contributors",
        "git_whoami", "whoami",
    ]

    ACTIONS_PROMPT = """
GIT MANAGEMENT (category: "git"):
  git_status       params: {}                                    ← working tree status
  git_log          params: {"count":10,"oneline":true}          ← commit history
  git_diff         params: {"file":"optional","staged":false}   ← show changes
  git_add          params: {"file":"filename or ."}             ← stage file(s)
  git_add_all      params: {}                                    ← stage all changes
  git_commit       params: {"message":"your commit message"}    ← commit staged changes
  git_push         params: {"remote":"origin","branch":"main"}  ← push to remote
  git_pull         params: {"remote":"origin","branch":"main"}  ← pull from remote
  git_fetch        params: {"remote":"origin"}                  ← fetch without merge
  git_clone        params: {"url":"https://...","path":"dest"}  ← clone a repo
  git_init         params: {"path":"optional dir"}              ← init new repo
  git_branches     params: {}                                    ← list all branches
  git_checkout     params: {"branch":"main"}                    ← switch branch
  git_branch_create params: {"branch":"feature/x"}             ← create new branch
  git_branch_delete params: {"branch":"old-branch"}            ← delete branch
  git_merge        params: {"branch":"feature/x"}              ← merge branch
  git_rebase       params: {"branch":"main"}                    ← rebase onto branch
  git_stash        params: {"message":"optional label"}         ← stash changes
  git_stash_pop    params: {}                                    ← restore last stash
  git_stash_list   params: {}                                    ← list stashes
  git_reset        params: {"mode":"soft|mixed|hard","ref":"HEAD~1"}
  git_revert       params: {"commit":"abc123"}                  ← safe undo commit
  git_tag          params: {"name":"v1.0","message":"Release"}  ← create tag
  git_remote       params: {}                                    ← list remotes
  git_remote_add   params: {"name":"origin","url":"https://..."}
  git_blame        params: {"file":"filename"}                  ← who changed each line
  git_summary      params: {}                                    ← full repo overview
  git_whoami       params: {}                                    ← show git identity
  git_config       params: {"key":"user.name","value":"John"}   ← set git config
  git_clean        params: {"force":false}                      ← remove untracked files
  git_amend        params: {"message":"optional new message"}   ← amend last commit
  git_cherry_pick  params: {"commit":"abc123"}                  ← apply specific commit
  git_show         params: {"ref":"HEAD"}                       ← show commit details
  git_contributors params: {}                                    ← list contributors

  Examples:
  "what is the git status"  → {"category":"git","action":"git_status","params":{},"message":"Checking git status."}
  "commit with message fix bug" → {"category":"git","action":"git_commit","params":{"message":"fix bug"},"message":"Committing."}
  "push to origin main"     → {"category":"git","action":"git_push","params":{"remote":"origin","branch":"main"},"message":"Pushing."}
  "create branch feature/x" → {"category":"git","action":"git_branch_create","params":{"branch":"feature/x"},"message":"Creating branch."}
  "show last 5 commits"     → {"category":"git","action":"git_log","params":{"count":5,"oneline":true},"message":"Showing log."}"""

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def handle(self, action: str, params: dict) -> str:
        dispatch = {
            # setup
            "git_init":         self._init,
            "init":             self._init,
            "git_clone":        self._clone,
            "clone":            self._clone,
            "git_config":       self._config,
            "config":           self._config,
            # info
            "git_status":       self._status,
            "status":           self._status,
            "git_log":          self._log,
            "log":              self._log,
            "git_diff":         self._diff,
            "diff":             self._diff,
            "git_show":         self._show,
            "show":             self._show,
            "git_blame":        self._blame,
            "blame":            self._blame,
            "git_remote":       self._remote,
            "remote":           self._remote,
            "list_remotes":     self._remote,
            "git_tags":         self._list_tags,
            "tags":             self._list_tags,
            "list_tags":        self._list_tags,
            "git_branches":     self._branches,
            "branches":         self._branches,
            "list_branches":    self._branches,
            "git_stash_list":   self._stash_list,
            "stash_list":       self._stash_list,
            # staging
            "git_add":          self._add,
            "add":              self._add,
            "stage":            self._add,
            "git_add_all":      self._add_all,
            "add_all":          self._add_all,
            "stage_all":        self._add_all,
            "git_unstage":      self._unstage,
            "unstage":          self._unstage,
            "reset_head":       self._unstage,
            "git_discard":      self._discard,
            "discard":          self._discard,
            "checkout_file":    self._discard,
            # committing
            "git_commit":       self._commit,
            "commit":           self._commit,
            "git_amend":        self._amend,
            "amend":            self._amend,
            # remote sync
            "git_push":         self._push,
            "push":             self._push,
            "git_pull":         self._pull,
            "pull":             self._pull,
            "git_fetch":        self._fetch,
            "fetch":            self._fetch,
            # branching
            "git_branch_create": self._branch_create,
            "create_branch":    self._branch_create,
            "new_branch":       self._branch_create,
            "git_branch_delete": self._branch_delete,
            "delete_branch":    self._branch_delete,
            "git_checkout":     self._checkout,
            "checkout":         self._checkout,
            "switch_branch":    self._checkout,
            "git_merge":        self._merge,
            "merge":            self._merge,
            "git_rebase":       self._rebase,
            "rebase":           self._rebase,
            "git_cherry_pick":  self._cherry_pick,
            "cherry_pick":      self._cherry_pick,
            # stashing
            "git_stash":        self._stash,
            "stash":            self._stash,
            "git_stash_pop":    self._stash_pop,
            "stash_pop":        self._stash_pop,
            "git_stash_drop":   self._stash_drop,
            "stash_drop":       self._stash_drop,
            # undoing
            "git_reset":        self._reset,
            "reset":            self._reset,
            "git_revert":       self._revert,
            "revert":           self._revert,
            "git_clean":        self._clean,
            "clean":            self._clean,
            # tagging
            "git_tag":          self._tag,
            "tag":              self._tag,
            "git_tag_delete":   self._tag_delete,
            "delete_tag":       self._tag_delete,
            # remote management
            "git_remote_add":   self._remote_add,
            "add_remote":       self._remote_add,
            "git_remote_remove": self._remote_remove,
            "remove_remote":    self._remote_remove,
            # summary / info
            "git_summary":      self._summary,
            "summary":          self._summary,
            "repo_summary":     self._summary,
            "git_contributors": self._contributors,
            "contributors":     self._contributors,
            "git_whoami":       self._whoami,
            "whoami":           self._whoami,
        }
        fn = dispatch.get(action)
        if fn:
            return fn(params)
        return f"  Unknown git action: '{action}'"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _repo(self, params: dict) -> str:
        """Get repo path from params or find it from CWD."""
        path = params.get("path", params.get("repo", ""))
        if path:
            return os.path.abspath(os.path.expanduser(path))
        found = _find_repo()
        if not found:
            return os.getcwd()
        return found

    def _check_git(self) -> str | None:
        """Return error if git not installed."""
        if not shutil.which("git"):
            return (
                "  ⚠️  git is not installed.\n"
                "  Install: sudo apt install git"
            )
        return None

    def _is_repo(self, path: str) -> bool:
        return os.path.isdir(os.path.join(path, ".git"))

    def _fmt(self, output: str, header: str = "") -> str:
        """Format git output nicely."""
        if not output or output.strip() == "":
            return "  (no output)"
        lines = output.splitlines()
        result = ""
        if header:
            result += f"  {header}\n  {_sep()}\n"
        for line in lines:
            result += f"  {line}\n"
        return result.rstrip()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _init(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        path = params.get("path", os.getcwd())
        path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(path, exist_ok=True)
        out = _git("init", cwd=path)
        return (f"  🗂️  Git repository initialized\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}\n"
                f"  Location: {path}")

    def _clone(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        url  = params.get("url", params.get("repo", params.get("link", ""))).strip()
        dest = params.get("path", params.get("destination", params.get("name", "")))
        if not url:
            return "  ⚠️  No URL specified. Use url='https://github.com/...'"
        args = ["clone", url]
        if dest:
            dest = os.path.abspath(os.path.expanduser(dest))
            args.append(dest)
        out = _git(*args, timeout=120)
        return (f"  📥 Cloning: {url}\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _config(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        key   = params.get("key", params.get("name", ""))
        value = params.get("value", params.get("setting", ""))
        scope = "--global" if params.get("global", True) else "--local"

        if not key:
            # Show current config
            out = _git("config", "--list", "--global")
            return f"  ⚙️  Git Config (global):\n  {_sep()}\n{self._fmt(out)}"

        if not value:
            # Get a specific key
            out = _git("config", scope, "--get", key)
            return f"  ⚙️  {key} = {out}"

        out = _git("config", scope, key, value)
        return f"  ⚙️  Set {key} = {value}"

    # ── Info ──────────────────────────────────────────────────────────────────

    def _status(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        if not self._is_repo(repo):
            return f"  ⚠️  Not a git repository: {repo}"

        code, out, err_msg = _run(["git", "status"], cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"

        # Parse status for a nicer summary
        lines     = out.splitlines()
        branch    = ""
        staged    = []
        unstaged  = []
        untracked = []

        for line in lines:
            if line.startswith("On branch"):
                branch = line.replace("On branch ", "").strip()
            elif line.startswith("\tmodified:") or "modified:" in line:
                f = line.strip().replace("modified:", "").strip()
                if "Changes to be committed" in "\n".join(lines[:lines.index(line)]):
                    staged.append(f"  modified:  {f}")
                else:
                    unstaged.append(f"  modified:  {f}")
            elif "new file:" in line:
                staged.append(f"  new file:  {line.strip().replace('new file:', '').strip()}")
            elif "deleted:" in line:
                (staged if "Changes to be committed" in out[:out.index(line)] else unstaged).append(
                    f"  deleted:   {line.strip().replace('deleted:', '').strip()}")
            elif line.startswith("\t") and "Changes not staged" in "\n".join(lines):
                pass

        result = f"  📊 Git Status  [{branch or 'unknown branch'}]\n  {_sep()}\n"
        result += self._fmt(out)
        return result

    def _log(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo    = self._repo(params)
        count   = int(params.get("count", params.get("n", params.get("limit", 10))))
        oneline = params.get("oneline", params.get("short", True))
        author  = params.get("author", "")
        since   = params.get("since", params.get("after", ""))
        file_   = params.get("file", params.get("path_filter", ""))

        args = ["log", f"-{count}"]
        if oneline:
            args += ["--pretty=format:%C(yellow)%h%Creset %C(cyan)%ad%Creset %s %C(green)(%an)%Creset",
                     "--date=short"]
        else:
            args += ["--pretty=format:%h | %ad | %s | %an", "--date=short"]

        if author:   args += [f"--author={author}"]
        if since:    args += [f"--since={since}"]
        if file_:    args += ["--", file_]

        code, out, err_msg = _run(["git"] + args, cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        if not out:
            return "  ℹ️  No commits found."

        return (f"  📜 Last {count} commit(s):\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _diff(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        file_  = params.get("file", params.get("path", ""))
        staged = params.get("staged", params.get("cached", False))

        args = ["diff"]
        if staged: args.append("--cached")
        if file_:  args.append(file_)

        code, out, err_msg = _run(["git"] + args, cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        if not out:
            return "  ℹ️  No differences found."

        lines   = out.splitlines()
        preview = "\n".join(f"  {l}" for l in lines[:60])
        extra   = f"\n  ... ({len(lines)-60} more lines)" if len(lines) > 60 else ""
        label   = "Staged diff" if staged else "Working tree diff"
        return (f"  🔍 {label}:\n"
                f"  {_sep()}\n"
                f"{preview}{extra}")

    def _show(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        ref  = params.get("ref", params.get("commit", params.get("hash", "HEAD")))
        code, out, err_msg = _run(["git", "show", "--stat", ref], cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        lines   = out.splitlines()
        preview = "\n".join(f"  {l}" for l in lines[:40])
        extra   = f"\n  ... ({len(lines)-40} more lines)" if len(lines) > 40 else ""
        return (f"  📦 Commit: {ref}\n"
                f"  {_sep()}\n"
                f"{preview}{extra}")

    def _blame(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo  = self._repo(params)
        file_ = params.get("file", params.get("path", params.get("filename", "")))
        if not file_:
            return "  ⚠️  No file specified. Use file='filename.py'"
        code, out, err_msg = _run(["git", "blame", "--date=short", file_], cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        lines   = out.splitlines()
        preview = "\n".join(f"  {l}" for l in lines[:30])
        extra   = f"\n  ... ({len(lines)-30} more lines)" if len(lines) > 30 else ""
        return (f"  👤 Blame: {file_}\n"
                f"  {_sep()}\n"
                f"{preview}{extra}")

    def _remote(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        code, out, err_msg = _run(["git", "remote", "-v"], cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        if not out:
            return "  ℹ️  No remotes configured."
        return (f"  🌐 Remotes:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _list_tags(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        code, out, err_msg = _run(["git", "tag", "--sort=-version:refname"], cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        if not out:
            return "  ℹ️  No tags found."
        return (f"  🏷️  Tags:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _branches(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        all_ = params.get("all", params.get("remote", False))
        args = ["branch", "-vv"]
        if all_: args.append("-a")
        code, out, err_msg = _run(["git"] + args, cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        return (f"  🌿 Branches:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _stash_list(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        code, out, err_msg = _run(["git", "stash", "list"], cwd=repo)
        if code != 0:
            return f"  ⚠️  {err_msg}"
        if not out:
            return "  ℹ️  No stashes."
        return (f"  📦 Stash list:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    # ── Staging ───────────────────────────────────────────────────────────────

    def _add(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo  = self._repo(params)
        file_ = params.get("file", params.get("path", params.get("files", ".")))
        if isinstance(file_, list):
            file_ = " ".join(file_)
        out = _git("add", file_, cwd=repo)
        status = _git("status", "--short", cwd=repo)
        return (f"  ✅ Staged: {file_}\n"
                f"  {_sep()}\n"
                f"{self._fmt(status)}")

    def _add_all(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        _git("add", "-A", cwd=repo)
        status = _git("status", "--short", cwd=repo)
        return (f"  ✅ Staged all changes\n"
                f"  {_sep()}\n"
                f"{self._fmt(status)}")

    def _unstage(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo  = self._repo(params)
        file_ = params.get("file", params.get("path", "."))
        out   = _git("reset", "HEAD", file_, cwd=repo)
        return f"  ↩️  Unstaged: {file_}\n{self._fmt(out)}"

    def _discard(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo  = self._repo(params)
        file_ = params.get("file", params.get("path", ""))
        if not file_:
            return "  ⚠️  No file specified."
        out = _git("checkout", "--", file_, cwd=repo)
        return f"  ↩️  Discarded changes in: {file_}"

    # ── Committing ────────────────────────────────────────────────────────────

    def _commit(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo    = self._repo(params)
        message = params.get("message", params.get("msg", params.get("m", ""))).strip()
        if not message:
            return "  ⚠️  No commit message. Use message='your message here'"
        out = _git("commit", "-m", message, cwd=repo)
        return (f"  💾 Committed:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _amend(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo    = self._repo(params)
        message = params.get("message", params.get("msg", ""))
        if message:
            out = _git("commit", "--amend", "-m", message, cwd=repo)
        else:
            out = _git("commit", "--amend", "--no-edit", cwd=repo)
        return (f"  ✏️  Amended last commit:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    # ── Remote Sync ───────────────────────────────────────────────────────────

    def _push(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        remote = params.get("remote", params.get("origin", "origin"))
        branch = params.get("branch", params.get("ref", ""))
        force  = params.get("force", params.get("f", False))
        tags   = params.get("tags", False)

        args = ["push", remote]
        if branch: args.append(branch)
        if force:  args.append("--force")
        if tags:   args.append("--tags")

        out = _git(*args, cwd=repo, timeout=120)
        icon = "🚀" if "error" not in out.lower() else "⚠️ "
        return (f"  {icon} Push → {remote}/{branch or 'current branch'}:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _pull(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        remote = params.get("remote", params.get("origin", "origin"))
        branch = params.get("branch", params.get("ref", ""))
        rebase = params.get("rebase", False)

        args = ["pull"]
        if rebase: args.append("--rebase")
        args.append(remote)
        if branch: args.append(branch)

        out = _git(*args, cwd=repo, timeout=120)
        return (f"  ⬇️  Pull ← {remote}/{branch or 'current branch'}:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _fetch(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        remote = params.get("remote", params.get("origin", "origin"))
        all_   = params.get("all", False)
        args   = ["fetch", "--all"] if all_ else ["fetch", remote]
        out    = _git(*args, cwd=repo, timeout=120)
        return (f"  🔄 Fetched from {remote}:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    # ── Branching ─────────────────────────────────────────────────────────────

    def _branch_create(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        branch = params.get("branch", params.get("name", params.get("ref", ""))).strip()
        if not branch:
            return "  ⚠️  No branch name specified."
        checkout = params.get("checkout", params.get("switch", True))
        if checkout:
            out = _git("checkout", "-b", branch, cwd=repo)
            return (f"  🌿 Created and switched to branch: '{branch}'\n"
                    f"  {_sep()}\n{self._fmt(out)}")
        else:
            out = _git("branch", branch, cwd=repo)
            return f"  🌿 Created branch: '{branch}'"

    def _branch_delete(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        branch = params.get("branch", params.get("name", "")).strip()
        if not branch:
            return "  ⚠️  No branch name specified."
        force  = params.get("force", False)
        flag   = "-D" if force else "-d"
        out    = _git("branch", flag, branch, cwd=repo)
        return (f"  🗑️  Deleted branch: '{branch}'\n"
                f"{self._fmt(out)}")

    def _checkout(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        branch = params.get("branch", params.get("ref", params.get("name", ""))).strip()
        if not branch:
            return "  ⚠️  No branch specified."
        out = _git("checkout", branch, cwd=repo)
        return (f"  🔀 Switched to: '{branch}'\n"
                f"{self._fmt(out)}")

    def _merge(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo    = self._repo(params)
        branch  = params.get("branch", params.get("ref", params.get("from", ""))).strip()
        if not branch:
            return "  ⚠️  No branch to merge specified."
        no_ff   = params.get("no_ff", params.get("no_fast_forward", False))
        args    = ["merge"]
        if no_ff: args.append("--no-ff")
        args.append(branch)
        out = _git(*args, cwd=repo)
        return (f"  🔀 Merged '{branch}':\n"
                f"  {_sep()}\n{self._fmt(out)}")

    def _rebase(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        branch = params.get("branch", params.get("onto", params.get("ref", ""))).strip()
        if not branch:
            return "  ⚠️  No branch to rebase onto specified."
        out = _git("rebase", branch, cwd=repo)
        return (f"  ⚡ Rebased onto '{branch}':\n"
                f"  {_sep()}\n{self._fmt(out)}")

    def _cherry_pick(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        commit = params.get("commit", params.get("hash", params.get("ref", ""))).strip()
        if not commit:
            return "  ⚠️  No commit hash specified."
        out = _git("cherry-pick", commit, cwd=repo)
        return (f"  🍒 Cherry-picked: {commit}\n"
                f"  {_sep()}\n{self._fmt(out)}")

    # ── Stashing ──────────────────────────────────────────────────────────────

    def _stash(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo    = self._repo(params)
        message = params.get("message", params.get("msg", params.get("label", ""))).strip()
        args    = ["stash", "push"]
        if message: args += ["-m", message]
        out = _git(*args, cwd=repo)
        return (f"  📦 Stashed changes{': ' + message if message else ''}:\n"
                f"  {_sep()}\n{self._fmt(out)}")

    def _stash_pop(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo  = self._repo(params)
        index = params.get("index", params.get("n", ""))
        args  = ["stash", "pop"]
        if index != "": args.append(f"stash@{{{index}}}")
        out = _git(*args, cwd=repo)
        return (f"  📤 Restored stash:\n"
                f"  {_sep()}\n{self._fmt(out)}")

    def _stash_drop(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo  = self._repo(params)
        index = params.get("index", params.get("n", "0"))
        out   = _git("stash", "drop", f"stash@{{{index}}}", cwd=repo)
        return f"  🗑️  Dropped stash@{{{index}}}\n{self._fmt(out)}"

    # ── Undoing ───────────────────────────────────────────────────────────────

    def _reset(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        mode = params.get("mode", params.get("type", "mixed")).lower()
        ref  = params.get("ref", params.get("commit", params.get("to", "HEAD~1")))

        if mode not in ("soft", "mixed", "hard"):
            mode = "mixed"

        if mode == "hard":
            warning = (
                f"  ⚠️  Hard reset to {ref} — this DISCARDS all uncommitted changes!\n"
                f"  {_sep()}\n"
            )
        else:
            warning = ""

        out = _git("reset", f"--{mode}", ref, cwd=repo)
        return (f"  {warning}  ↩️  Reset ({mode}) to {ref}:\n"
                f"  {_sep()}\n{self._fmt(out)}")

    def _revert(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo   = self._repo(params)
        commit = params.get("commit", params.get("hash", params.get("ref", "HEAD"))).strip()
        no_edit = params.get("no_edit", True)
        args   = ["revert", commit]
        if no_edit: args.append("--no-edit")
        out = _git(*args, cwd=repo)
        return (f"  ↩️  Reverted commit {commit}:\n"
                f"  {_sep()}\n{self._fmt(out)}")

    def _clean(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo    = self._repo(params)
        force   = params.get("force", params.get("f", False))
        dirs    = params.get("dirs", params.get("d", False))
        dry_run = params.get("dry_run", params.get("preview", not force))

        if dry_run:
            args = ["clean", "-n"]
            if dirs: args.append("-d")
            out = _git(*args, cwd=repo)
            return (f"  🧹 Would remove (dry run):\n"
                    f"  {_sep()}\n{self._fmt(out)}\n"
                    f"  Use force=true to actually delete.")
        else:
            args = ["clean", "-f"]
            if dirs: args.append("-d")
            out = _git(*args, cwd=repo)
            return (f"  🧹 Cleaned untracked files:\n"
                    f"  {_sep()}\n{self._fmt(out)}")

    # ── Tagging ───────────────────────────────────────────────────────────────

    def _tag(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo    = self._repo(params)
        name    = params.get("name", params.get("tag", params.get("version", ""))).strip()
        message = params.get("message", params.get("msg", "")).strip()
        ref     = params.get("ref", params.get("commit", ""))

        if not name:
            return "  ⚠️  No tag name specified."

        args = ["tag"]
        if message:
            args += ["-a", name, "-m", message]
        else:
            args.append(name)
        if ref:
            args.append(ref)

        out = _git(*args, cwd=repo)
        kind = "annotated" if message else "lightweight"
        return f"  🏷️  Created {kind} tag: '{name}'"

    def _tag_delete(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        name = params.get("name", params.get("tag", "")).strip()
        if not name:
            return "  ⚠️  No tag name specified."
        out = _git("tag", "-d", name, cwd=repo)
        return f"  🗑️  Deleted tag: '{name}'"

    # ── Remote Management ─────────────────────────────────────────────────────

    def _remote_add(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        name = params.get("name", params.get("remote", "origin")).strip()
        url  = params.get("url", params.get("link", "")).strip()
        if not url:
            return "  ⚠️  No URL specified."
        out = _git("remote", "add", name, url, cwd=repo)
        return f"  🌐 Added remote '{name}' → {url}"

    def _remote_remove(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        name = params.get("name", params.get("remote", "")).strip()
        if not name:
            return "  ⚠️  No remote name specified."
        out = _git("remote", "remove", name, cwd=repo)
        return f"  🗑️  Removed remote: '{name}'"

    # ── Summary ───────────────────────────────────────────────────────────────

    def _summary(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        if not self._is_repo(repo):
            return f"  ⚠️  Not a git repository: {repo}"

        # Collect all info
        _, branch_out, _  = _run(["git", "branch", "--show-current"], cwd=repo)
        _, remote_out, _  = _run(["git", "remote", "-v"], cwd=repo)
        _, log_out, _     = _run(["git", "log", "--oneline", "-5"], cwd=repo)
        _, status_out, _  = _run(["git", "status", "--short"], cwd=repo)
        _, count_out, _   = _run(["git", "rev-list", "--count", "HEAD"], cwd=repo)
        _, tags_out, _    = _run(["git", "tag"], cwd=repo)
        _, stash_out, _   = _run(["git", "stash", "list"], cwd=repo)

        tag_count   = len(tags_out.splitlines()) if tags_out else 0
        stash_count = len(stash_out.splitlines()) if stash_out else 0

        result = (
            f"  📁 Repository Summary\n"
            f"  {_sep()}\n"
            f"  📂 Path:     {repo}\n"
            f"  🌿 Branch:   {branch_out or 'unknown'}\n"
            f"  📦 Commits:  {count_out or '?'}\n"
            f"  🏷️  Tags:     {tag_count}\n"
            f"  📦 Stashes:  {stash_count}\n"
        )

        if remote_out:
            result += f"  {_sep()}\n  🌐 Remotes:\n"
            for line in remote_out.splitlines()[:4]:
                result += f"    {line}\n"

        if status_out:
            result += f"  {_sep()}\n  📝 Uncommitted changes:\n"
            for line in status_out.splitlines()[:10]:
                result += f"    {line}\n"
        else:
            result += f"  {_sep()}\n  ✅ Working tree clean\n"

        if log_out:
            result += f"  {_sep()}\n  📜 Recent commits:\n"
            for line in log_out.splitlines():
                result += f"    {line}\n"

        return result.rstrip()

    def _contributors(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        repo = self._repo(params)
        if not self._is_repo(repo):
            return f"  ⚠️  Not a git repository: {repo}"
        code, out, err_msg = _run(
            ["git", "shortlog", "-sn", "--all"], cwd=repo
        )
        if code != 0:
            return f"  ⚠️  {err_msg}"
        if not out:
            return "  ℹ️  No commits yet."
        return (f"  👥 Contributors:\n"
                f"  {_sep()}\n"
                f"{self._fmt(out)}")

    def _whoami(self, params: dict) -> str:
        err = self._check_git()
        if err: return err
        _, name,  _ = _run(["git", "config", "--get", "user.name"])
        _, email, _ = _run(["git", "config", "--get", "user.email"])
        if not name and not email:
            return (
                "  ⚠️  Git identity not configured.\n"
                "  Set it with:\n\n"
                "    git config --global user.name \"Your Name\"\n"
                "    git config --global user.email \"you@example.com\""
            )
        return (f"  👤 Git Identity:\n"
                f"  {_sep()}\n"
                f"  Name:  {name or '(not set)'}\n"
                f"  Email: {email or '(not set)'}")
