"""
JARVIS Plugin: File & Folder Management
=======================================
Full file system operations for a Linux power user.
"""

import os
import shutil
import glob
import stat
import zipfile
import tarfile
import hashlib
import subprocess
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

from core.plugin_base import JarvisPlugin


# ── Helpers ────────────────────────────────────────────────────────────────────

def expand(path: str) -> str:
    return os.path.abspath(os.path.expanduser(str(path)))


def _fmt_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def _resolve_glob(path: str) -> list:
    if any(c in path for c in ("*", "?")):
        return sorted(glob.glob(path))
    return [path] if os.path.exists(path) else []


def _sep(n=48):
    return "  " + "─" * n


# ── Plugin ─────────────────────────────────────────────────────────────────────

class FilesPlugin(JarvisPlugin):
    NAME        = "files"
    CATEGORY    = "file"
    DESCRIPTION = "Complete file & folder management for Linux"
    ACTIONS     = [
        # listing
        "list_files", "list", "list_directory", "show", "show_files",
        "tree", "directory_tree", "folder_tree",
        # reading
        "read", "read_file", "cat", "view", "show_content", "display",
        "head", "tail",
        # writing
        "write_file", "write", "create_file", "create", "new_file", "make_file",
        "edit_file", "edit", "modify", "modify_file", "update", "update_file",
        "append_file", "append", "append_to_file", "add_to_file",
        # copy / move
        "move", "move_file",
        "move_by_type",
        "copy", "copy_file",
        "copy_contents",
        # delete
        "delete", "delete_folder", "delete_file", "remove", "remove_folder", "remove_file",
        "delete_by_type", "delete_by_extension", "remove_by_type",
        "delete_all", "clear_folder", "remove_all",
        # rename / duplicate
        "rename",
        "rename_bulk", "batch_rename",
        "duplicate", "duplicate_file",
        # search & info
        "search", "find", "find_file",
        "find_by_size", "find_large_files",
        "find_by_date", "find_recent",
        "find_duplicates", "duplicates",
        "file_info", "info", "stat", "details", "properties",
        "count_files", "count", "how_many",
        "disk_usage",
        # organize
        "create_folder", "mkdir", "make_directory", "new_folder",
        "organize",
        # archive
        "compress", "zip", "archive", "tar", "pack",
        "extract", "unzip", "untar", "decompress", "unpack",
        # permissions & ownership
        "chmod", "change_permissions",
        "chown", "change_owner",
        # symlinks
        "symlink", "create_symlink", "ln",
        # open
        "open_file", "open_with",
        # advanced
        "grep", "grep_file", "search_in_files", "find_text",
        "word_count", "wc", "count_words",
        "compare", "compare_files", "diff",
        "backup", "backup_file",
        "watch_file", "watch",
        "merge_files", "merge", "combine",
        "hide_file", "unhide_file", "set_hidden",
    ]

    ACTIONS_PROMPT = """
FILE ACTIONS (category: "file"):
  list_files      params: {"path":"..."}
  tree            params: {"path":"...","depth":3}
  read            params: {"path":"..."}
  head            params: {"path":"...","lines":10}
  tail            params: {"path":"...","lines":10}
  write_file      params: {"path":"...","content":"..."}
  edit_file       params: {"path":"...","instruction":"what to change"}
  append_file     params: {"path":"...","content":"..."}
  create_folder   params: {"path":"..."}
  delete          params: {"path":"..."}
  delete_all      params: {"path":"..."}
  delete_by_type  params: {"path":"...","extension":"jpeg"}
  move            params: {"source":"...","destination":"..."}
  move_by_type    params: {"extension":"pdf","source":"...","destination":"..."}
  copy            params: {"source":"...","destination":"..."}
  copy_contents   params: {"source":"...","destination":"..."}
  rename          params: {"source":"...","new_name":"..."}
  rename_bulk     params: {"path":"...","mode":"replace|prefix|suffix","find":"...","replace":"..."}
  duplicate       params: {"source":"...","new_name":"..."}
  search          params: {"name":"...","directory":"..."}
  find_by_size    params: {"path":"...","min_mb":100}
  find_recent     params: {"path":"...","days":7}
  find_duplicates params: {"path":"..."}
  file_info       params: {"path":"..."}
  count_files     params: {"path":"...","extension":"py"}
  disk_usage      params: {"path":"..."}
  organize        params: {"path":"..."}
  compress        params: {"source":"...","output":"...","format":"zip"}
  extract         params: {"source":"...","destination":"..."}
  chmod           params: {"path":"...","mode":"755"}
  chown           params: {"path":"...","owner":"user:group"}
  symlink         params: {"target":"...","link":"..."}
  open_file       params: {"path":"..."}
  change_dir      params: {"path":"..."}
  grep            params: {"pattern":"TODO","path":"...","extension":"py"}
  word_count      params: {"path":"..."}
  compare_files   params: {"file1":"...","file2":"..."}
  backup_file     params: {"path":"...","destination":"..."}
  watch_file      params: {"path":"...","lines":20}
  merge_files     params: {"sources":["file1","file2"],"output":"..."}
  hide_file       params: {"path":"...","hide":true}"""

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def handle(self, action: str, params: dict) -> str:
        if action in ("list_files", "list", "list_directory", "show", "show_files"):
            return self._list_files(params)
        elif action in ("tree", "directory_tree", "folder_tree"):
            return self._tree(params)
        elif action in ("read", "read_file", "cat", "view", "show_content", "display"):
            return self._read_file(params)
        elif action == "head":
            return self._head(params)
        elif action == "tail":
            return self._tail(params)
        elif action in ("write_file", "write", "create_file", "create", "new_file", "make_file"):
            return self._write_file(params)
        elif action in ("edit_file", "edit", "modify", "modify_file", "update", "update_file"):
            return self._edit_file(params)
        elif action in ("append_file", "append", "append_to_file", "add_to_file"):
            return self._append_file(params)
        elif action in ("move", "move_file"):
            return self._move_file(params)
        elif action == "move_by_type":
            return self._move_by_type(params)
        elif action in ("copy", "copy_file"):
            return self._copy_file(params)
        elif action == "copy_contents":
            return self._copy_contents(params)
        elif action in ("delete", "delete_folder", "delete_file",
                        "remove", "remove_folder", "remove_file"):
            return self._delete(params)
        elif action in ("delete_by_type", "delete_by_extension", "remove_by_type"):
            return self._delete_by_type(params)
        elif action in ("delete_all", "clear_folder", "remove_all"):
            return self._delete_all(params)
        elif action == "rename":
            return self._rename(params)
        elif action in ("rename_bulk", "batch_rename"):
            return self._rename_bulk(params)
        elif action in ("duplicate", "duplicate_file"):
            return self._duplicate(params)
        elif action in ("search", "find", "find_file"):
            return self._search(params)
        elif action in ("find_by_size", "find_large_files"):
            return self._find_by_size(params)
        elif action in ("find_by_date", "find_recent"):
            return self._find_recent(params)
        elif action in ("find_duplicates", "duplicates"):
            return self._find_duplicates(params)
        elif action in ("file_info", "info", "stat", "details", "properties"):
            return self._file_info(params)
        elif action in ("count_files", "count", "how_many"):
            return self._count_files(params)
        elif action == "disk_usage":
            return self._disk_usage(params)
        elif action in ("create_folder", "mkdir", "make_directory", "new_folder"):
            return self._create_folder(params)
        elif action == "organize":
            return self._organize(params)
        elif action in ("compress", "zip", "archive", "tar", "pack"):
            return self._compress(params)
        elif action in ("extract", "unzip", "untar", "decompress", "unpack"):
            return self._extract(params)
        elif action in ("chmod", "change_permissions"):
            return self._chmod(params)
        elif action in ("chown", "change_owner"):
            return self._chown(params)
        elif action in ("symlink", "create_symlink", "ln"):
            return self._symlink(params)
        elif action in ("open_file", "open_with"):
            return self._open_file(params)
        return f"Unknown file action: '{action}'"

    # ── Listing ───────────────────────────────────────────────────────────────

    def _list_files(self, params):
        path        = expand(params.get("path", params.get("directory", "~")))
        ext         = params.get("extension", "")
        show_hidden = params.get("hidden", False)

        if not os.path.exists(path):
            return f"Directory not found: {path}"

        entries = sorted(os.listdir(path))
        if not show_hidden:
            entries = [e for e in entries if not e.startswith(".")]
        if ext:
            entries = [e for e in entries if e.endswith(f".{ext.lstrip('.')}")]
        if not entries:
            return f"No files found in {path}"

        dirs  = [e for e in entries if os.path.isdir(os.path.join(path, e))]
        files = [e for e in entries if not os.path.isdir(os.path.join(path, e))]

        result  = f"\n  📂 {path}  ({len(dirs)} folders, {len(files)} files)\n"
        result += _sep() + "\n"
        for e in dirs:
            result += f"    📁  {e}/\n"
        for e in files:
            full = os.path.join(path, e)
            size = _fmt_size(os.path.getsize(full))
            result += f"    📄  {e:<42}{size}\n"
        total = len(entries)
        if total > 60:
            result += f"    ... and {total - 60} more items\n"
        return result

    def _tree(self, params):
        path      = expand(params.get("path", params.get("directory", ".")))
        max_depth = int(params.get("depth", 3))
        if not os.path.isdir(path):
            return f"Directory not found: {path}"
        lines = [f"  📁 {path}"]
        self._tree_walk(path, "  ", 0, max_depth, lines)
        if len(lines) > 80:
            lines = lines[:80] + [f"  ... (truncated at 80 entries)"]
        return "\n".join(lines)

    def _tree_walk(self, path, prefix, depth, max_depth, lines):
        if depth >= max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return
        for i, entry in enumerate(entries):
            full = os.path.join(path, entry)
            con  = "└── " if i == len(entries) - 1 else "├── "
            icon = "📁 " if os.path.isdir(full) else "📄 "
            lines.append(f"{prefix}{con}{icon}{entry}")
            if os.path.isdir(full):
                ext = "    " if i == len(entries) - 1 else "│   "
                self._tree_walk(full, prefix + ext, depth + 1, max_depth, lines)

    # ── Reading ───────────────────────────────────────────────────────────────

    def _read_file(self, params):
        path = expand(params.get("path", params.get("file", params.get("source", ""))))
        if not path:
            return "No file path specified."

        # If exact path not found, search cwd by name or extension
        if not os.path.exists(path):
            name = os.path.basename(path)
            ext  = os.path.splitext(path)[1]
            matches = list(Path(os.getcwd()).rglob(f"*{name}*")) if name else []
            if not matches and ext:
                matches = list(Path(os.getcwd()).rglob(f"*{ext}"))
            if matches:
                path = str(matches[0])
            else:
                return f"File not found: {path}"

        if os.path.isdir(path):
            return self._list_files({"path": path})

        try:
            with open(path, "r", errors="ignore") as f:
                content = f.read()
            lines   = content.splitlines()
            preview = "\n".join(lines[:100])
            note    = f"\n\n  ... ({len(lines)-100} more lines)" if len(lines) > 100 else ""
            return f"\n  📄 {path}\n{_sep()}\n{preview}{note}"
        except Exception as e:
            return f"Could not read file: {e}"

    def _head(self, params):
        path = expand(params.get("path", params.get("file", "")))
        n    = int(params.get("lines", 10))
        if not os.path.exists(path):
            return f"File not found: {path}"
        with open(path, "r", errors="ignore") as f:
            lines = [f.readline() for _ in range(n)]
        return f"  📄 {path} — first {n} lines\n{_sep()}\n" + "".join(lines)

    def _tail(self, params):
        path = expand(params.get("path", params.get("file", "")))
        n    = int(params.get("lines", 10))
        if not os.path.exists(path):
            return f"File not found: {path}"
        with open(path, "r", errors="ignore") as f:
            all_lines = f.readlines()
        return f"  📄 {path} — last {n} lines\n{_sep()}\n" + "".join(all_lines[-n:])

    # ── Writing ───────────────────────────────────────────────────────────────

    def _write_file(self, params):
        path    = expand(params.get("path", params.get("file", params.get("name", ""))))
        content = params.get("content", params.get("text", params.get("body", "")))
        if not path:
            return "No file path specified."
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return (f"  ✏️  Created: {os.path.basename(path)}\n"
                f"     Path:    {path}\n"
                f"     Size:    {_fmt_size(len(content.encode()))}  "
                f"({len(content.splitlines())} lines)")

    def _edit_file(self, params):
        path        = expand(params.get("path", params.get("file", "")))
        instruction = params.get("instruction", params.get("task", params.get("edit", "")))

        if not path:
            return "No file path specified."
        if os.path.isdir(path):
            return (f"'{os.path.basename(path)}' is a directory.\n"
                    f"Specify a file inside it, e.g. {path}/index.html")
        if not os.path.exists(path):
            return f"File not found: {path}"
        if not instruction:
            return "No instruction given. Tell me what to change."

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                original = f.read()
        except Exception as e:
            return f"Could not read file: {e}"

        if not original.strip():
            return f"File '{path}' is empty — nothing to edit."
        if not self.ai_client:
            return "AI client not available."

        try:
            response = self.ai_client.chat.completions.create(
                model=self.ai_model or "llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content":
                        "You are a file editor. Apply the instruction exactly and return "
                        "ONLY the updated file content. No explanations, no markdown fences."},
                    {"role": "user", "content":
                        f"INSTRUCTION: {instruction}\n\nFILE:\n{original}"},
                ],
                temperature=0.2,
                max_tokens=4000,
            )
            updated = response.choices[0].message.content
            if updated.startswith("```"):
                lines = updated.split("\n")
                end   = -1 if lines[-1].strip() == "```" else len(lines)
                updated = "\n".join(lines[1:end])
        except Exception as e:
            err = str(e)
            if "429" in err or "rate_limit" in err:
                return (
                    "  ⚠️  Groq rate limit reached (free tier: 100k tokens/day).\n\n"
                    "  Options:\n"
                    "    1. Wait until tomorrow for quota reset\n"
                    "    2. Upgrade at console.groq.com/settings/billing\n"
                    "    3. Set GROQ_MODEL= in your .env to use a different model"
                )
            return f"AI edit failed: {err}"

        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)

        return (f"  ✏️  Edited: {os.path.basename(path)}\n"
                f"     Before: {len(original.splitlines())} lines "
                f"({_fmt_size(len(original.encode()))})\n"
                f"     After:  {len(updated.splitlines())} lines "
                f"({_fmt_size(len(updated.encode()))})")

    def _append_file(self, params):
        path    = expand(params.get("path", params.get("file", "")))
        content = params.get("content", params.get("text", params.get("body", "")))
        if not path:    return "No file path specified."
        if not content: return "No content to append."
        existed = os.path.exists(path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(("\n" if existed else "") + content)
        verb = "Appended to" if existed else "Created"
        return f"  ✏️  {verb}: {os.path.basename(path)}  (+{_fmt_size(len(content.encode()))})"

    # ── Copy / Move ───────────────────────────────────────────────────────────

    def _copy_file(self, params):
        """
        Fixed copy:
          file  → dir/file : standard copy
          dir   → existing dir : copy CONTENTS into dst (dirs_exist_ok)
          dir   → new path : full copytree
        """
        src = expand(params.get("source", params.get("src", "")))
        dst = expand(params.get("destination", params.get("dest", params.get("dst", ""))))

        if not src or not dst:
            return "Missing source or destination."
        if not os.path.exists(src):
            return f"Source not found: {src}"

        if os.path.isfile(src):
            os.makedirs(dst if os.path.isdir(dst) else os.path.dirname(dst) or ".", exist_ok=True)
            dest_path = os.path.join(dst, os.path.basename(src)) if os.path.isdir(dst) else dst
            shutil.copy2(src, dest_path)
            return f"  📋 Copied: {os.path.basename(src)} → {dest_path}"

        # src is a directory
        if os.path.isdir(dst):
            # Destination exists — copy contents in using dirs_exist_ok
            return self._copy_contents({"source": src, "destination": dst})
        else:
            # Destination doesn't exist — create as full copy
            shutil.copytree(src, dst)
            return f"  📋 Copied folder: {os.path.basename(src)} → {dst}"

    def _copy_contents(self, params):
        """Copy every item inside src into dst without copying the folder itself."""
        src = expand(params.get("source", params.get("src", "")))
        dst = expand(params.get("destination", params.get("dest", params.get("dst", ""))))

        if not src or not dst:
            return "Missing source or destination."
        if not os.path.isdir(src):
            return f"Source is not a directory: {src}"

        os.makedirs(dst, exist_ok=True)
        copied, errors = [], []

        for entry in os.listdir(src):
            s = os.path.join(src, entry)
            d = os.path.join(dst, entry)
            try:
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
                copied.append(entry)
            except Exception as e:
                errors.append(f"{entry}: {e}")

        result = f"  📋 Copied {len(copied)} item(s) from {src}\n     → {dst}"
        if errors:
            result += f"\n  ⚠️  {len(errors)} error(s):\n    " + "\n    ".join(errors)
        return result

    def _move_file(self, params):
        src = expand(params.get("source", params.get("src", "")))
        dst = expand(params.get("destination", params.get("dest", params.get("dst", ""))))
        if not src or not dst:
            return "Missing source or destination."
        matches = _resolve_glob(src)
        if not matches:
            return f"Source not found: {src}"
        os.makedirs(dst if os.path.isdir(dst) or not os.path.splitext(dst)[1]
                    else os.path.dirname(dst) or ".", exist_ok=True)
        moved = []
        for f in matches:
            dest_path = os.path.join(dst, os.path.basename(f)) if os.path.isdir(dst) else dst
            shutil.move(f, dest_path)
            moved.append(os.path.basename(f))
        items = "\n    ".join(moved[:10])
        extra = f"\n    ... and {len(moved)-10} more" if len(moved) > 10 else ""
        return f"  📦 Moved {len(moved)} item(s) → {dst}\n    {items}{extra}"

    def _move_by_type(self, params):
        ext     = params.get("extension", "").lstrip(".")
        src_dir = expand(params.get("source", "~/Downloads"))
        dst_dir = expand(params.get("destination", "~/Documents"))
        os.makedirs(dst_dir, exist_ok=True)
        files = glob.glob(os.path.join(src_dir, f"*.{ext}"))
        if not files:
            return f"No .{ext} files found in {src_dir}"
        for f in files:
            shutil.move(f, os.path.join(dst_dir, os.path.basename(f)))
        return f"  📦 Moved {len(files)} .{ext} file(s) → {dst_dir}"

    # ── Delete ────────────────────────────────────────────────────────────────

    def _delete(self, params):
        path = expand(params.get("path", params.get("source", "")))
        if not path:
            return "No path specified."
        matches = _resolve_glob(path)
        if not matches:
            return f"Not found: {path}"
        deleted, errors = [], []
        for item in matches:
            try:
                if os.path.isdir(item): shutil.rmtree(item)
                else: os.remove(item)
                deleted.append(os.path.basename(item))
            except Exception as e:
                errors.append(f"{item}: {e}")
        result = f"  🗑️  Deleted: {', '.join(deleted[:10])}"
        if len(deleted) > 10:
            result += f" ... and {len(deleted)-10} more"
        if errors:
            result += f"\n  ⚠️  Errors: " + ", ".join(errors)
        return result

    def _delete_by_type(self, params):
        ext       = params.get("extension", "").lstrip(".")
        directory = expand(params.get("path", params.get("directory", os.getcwd())))
        if not ext:
            return "No extension specified. Example: extension=jpeg"
        if not os.path.isdir(directory):
            return f"Directory not found: {directory}"
        files = glob.glob(os.path.join(directory, f"*.{ext}"))
        if not files:
            return f"No .{ext} files found in {directory}"
        for f in files:
            os.remove(f)
        return f"  🗑️  Deleted {len(files)} .{ext} file(s) from {directory}"

    def _delete_all(self, params):
        path = expand(params.get("path", params.get("directory", os.getcwd())))
        if not os.path.isdir(path):
            return f"Directory not found: {path}"
        entries = os.listdir(path)
        if not entries:
            return f"  ℹ️  Already empty: {path}"
        deleted, errors = [], []
        for entry in entries:
            full = os.path.join(path, entry)
            try:
                if os.path.isdir(full): shutil.rmtree(full)
                else: os.remove(full)
                deleted.append(entry)
            except Exception as e:
                errors.append(f"{entry}: {e}")
        result = f"  🗑️  Deleted {len(deleted)} item(s) from {path}"
        if errors:
            result += f"\n  ⚠️  {len(errors)} error(s):\n    " + "\n    ".join(errors)
        return result

    # ── Rename / Duplicate ────────────────────────────────────────────────────

    def _rename(self, params):
        src      = expand(params.get("source", params.get("path", "")))
        new_name = params.get("new_name", params.get("destination", ""))
        if not src or not new_name:
            return "Missing source or new name."
        if not os.path.exists(src):
            return f"Not found: {src}"
        dst = os.path.join(os.path.dirname(src), new_name)
        os.rename(src, dst)
        return f"  ✏️  Renamed: '{os.path.basename(src)}' → '{new_name}'"

    def _rename_bulk(self, params):
        directory  = expand(params.get("path", params.get("directory", "")))
        mode       = params.get("mode", "replace").lower()
        ext_filter = params.get("extension", "").lstrip(".")
        if not os.path.isdir(directory):
            return f"Directory not found: {directory}"
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        if ext_filter:
            files = [f for f in files if f.endswith(f".{ext_filter}")]
        renamed = []
        if mode == "replace":
            find, replace = params.get("find", ""), params.get("replace", "")
            if not find: return "Provide 'find' text."
            for f in files:
                if find in f:
                    new = f.replace(find, replace)
                    os.rename(os.path.join(directory, f), os.path.join(directory, new))
                    renamed.append(f"'{f}' → '{new}'")
        elif mode == "prefix":
            prefix = params.get("prefix", "")
            if not prefix: return "Provide a 'prefix'."
            for f in files:
                new = prefix + f
                os.rename(os.path.join(directory, f), os.path.join(directory, new))
                renamed.append(f"'{f}' → '{new}'")
        elif mode == "suffix":
            suffix = params.get("suffix", "")
            if not suffix: return "Provide a 'suffix'."
            for f in files:
                base, e = os.path.splitext(f)
                new = base + suffix + e
                os.rename(os.path.join(directory, f), os.path.join(directory, new))
                renamed.append(f"'{f}' → '{new}'")
        else:
            return f"Unknown mode '{mode}'. Use: replace, prefix, suffix"
        if not renamed:
            return "No files matched."
        preview = "\n    ".join(renamed[:20])
        extra   = f"\n    ... and {len(renamed)-20} more" if len(renamed) > 20 else ""
        return f"  ✏️  Renamed {len(renamed)} file(s):\n    {preview}{extra}"

    def _duplicate(self, params):
        src      = expand(params.get("source", params.get("path", "")))
        new_name = params.get("new_name", "")
        if not os.path.exists(src):
            return f"Not found: {src}"
        if new_name:
            dst = os.path.join(os.path.dirname(src), new_name)
        else:
            base, ext = os.path.splitext(src)
            dst, n = f"{base}_copy{ext}", 1
            while os.path.exists(dst):
                dst = f"{base}_copy{n}{ext}"; n += 1
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return f"  📋 Duplicated → '{os.path.basename(dst)}'"

    # ── Search & Info ─────────────────────────────────────────────────────────

    def _search(self, params):
        name       = params.get("name", params.get("filename", params.get("query", "")))
        search_dir = expand(params.get("directory", params.get("path", "~")))
        ext        = params.get("extension", "")
        pattern    = params.get("pattern", "")

        if not os.path.isdir(search_dir):
            return f"Directory not found: {search_dir}"

        if pattern:
            matches = list(Path(search_dir).rglob(pattern))
        elif name:
            matches = list(Path(search_dir).rglob(f"*{name}*"))
        elif ext:
            matches = list(Path(search_dir).rglob(f"*.{ext.lstrip('.')}"))
        else:
            return "Provide a name, extension, or pattern to search for."

        if not matches:
            return f"  🔍 No matches found in {search_dir}"

        result = f"  🔍 Found {len(matches)} match(es) in {search_dir}:\n"
        for m in matches[:25]:
            icon = "📁" if m.is_dir() else "📄"
            size = f"  {_fmt_size(m.stat().st_size)}" if m.is_file() else ""
            result += f"    {icon}  {m}{size}\n"
        if len(matches) > 25:
            result += f"    ... and {len(matches)-25} more"
        return result

    def _find_by_size(self, params):
        path   = expand(params.get("path", "~"))
        min_mb = float(params.get("min_mb", params.get("min", 50)))
        max_mb = float(params.get("max_mb", params.get("max", float("inf"))))
        min_b, max_b = min_mb * 1024 * 1024, max_mb * 1024 * 1024

        if not os.path.isdir(path):
            return f"Directory not found: {path}"

        matches = []
        for f in Path(path).rglob("*"):
            if f.is_file():
                try:
                    s = f.stat().st_size
                    if min_b <= s <= max_b:
                        matches.append((s, str(f)))
                except PermissionError:
                    pass
        matches.sort(reverse=True)
        if not matches:
            return f"  No files larger than {min_mb}MB found in {path}"
        result = f"  🔍 {len(matches)} file(s) ≥ {min_mb}MB in {path}:\n"
        for size, fpath in matches[:20]:
            result += f"    📄  {_fmt_size(size):<12}  {fpath}\n"
        if len(matches) > 20:
            result += f"    ... and {len(matches)-20} more"
        return result

    def _find_recent(self, params):
        path = expand(params.get("path", "~"))
        days = int(params.get("days", 7))
        if not os.path.isdir(path):
            return f"Directory not found: {path}"
        cutoff  = time.time() - (days * 86400)
        matches = []
        for f in Path(path).rglob("*"):
            if f.is_file():
                try:
                    if f.stat().st_mtime >= cutoff:
                        matches.append((f.stat().st_mtime, str(f)))
                except PermissionError:
                    pass
        matches.sort(reverse=True)
        if not matches:
            return f"  No files modified in the last {days} day(s) in {path}"
        result = f"  🕐 {len(matches)} file(s) modified in last {days} day(s):\n"
        for mtime, fpath in matches[:20]:
            dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            result += f"    📄  {dt}  {fpath}\n"
        if len(matches) > 20:
            result += f"    ... and {len(matches)-20} more"
        return result

    def _find_duplicates(self, params):
        path = expand(params.get("path", params.get("directory", "~")))
        if not os.path.isdir(path):
            return f"Directory not found: {path}"

        # Group by size, then hash within groups for accuracy
        size_map = defaultdict(list)
        for f in Path(path).rglob("*"):
            if f.is_file():
                try:
                    size_map[f.stat().st_size].append(f)
                except PermissionError:
                    pass

        hash_map = defaultdict(list)
        for size, files in size_map.items():
            if len(files) < 2:
                continue
            for f in files:
                try:
                    h = hashlib.md5(f.read_bytes()).hexdigest()
                    hash_map[h].append(str(f))
                except Exception:
                    pass

        groups = {h: p for h, p in hash_map.items() if len(p) > 1}
        if not groups:
            return "  ✅ No duplicate files found."

        wasted = 0
        result = f"  🔍 Found {len(groups)} duplicate group(s):\n"
        for h, paths in list(groups.items())[:15]:
            size    = os.path.getsize(paths[0])
            wasted += size * (len(paths) - 1)
            result += f"\n    🔁 {_fmt_size(size)} each — {len(paths)} copies:\n"
            for p in paths:
                result += f"      📄 {p}\n"
        result += f"\n  💾 Space wasted: {_fmt_size(wasted)}"
        if len(groups) > 15:
            result += f"\n  ... and {len(groups)-15} more groups"
        return result

    def _file_info(self, params):
        path = expand(params.get("path", params.get("file", "")))
        if not os.path.exists(path):
            return f"Not found: {path}"
        s    = os.stat(path)
        kind = "Directory" if os.path.isdir(path) else "File"
        ext  = os.path.splitext(path)[1] or "(none)"

        link_info = ""
        if os.path.islink(path):
            link_info = f"\n    Symlink → {os.readlink(path)}"

        line_info = ""
        if os.path.isfile(path) and s.st_size < 10 * 1024 * 1024:
            try:
                with open(path, "r", errors="ignore") as f:
                    line_info = f"\n    Lines:    {sum(1 for _ in f)}"
            except Exception:
                pass

        dir_info = ""
        if os.path.isdir(path):
            items = len(os.listdir(path))
            dir_info = f"\n    Contents: {items} item(s)"

        return (
            f"\n  📋 {os.path.basename(path)}\n"
            f"{_sep(40)}\n"
            f"    Type:     {kind}  ({ext})\n"
            f"    Size:     {_fmt_size(s.st_size)}\n"
            f"    Modified: {datetime.fromtimestamp(s.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"    Created:  {datetime.fromtimestamp(s.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"    Accessed: {datetime.fromtimestamp(s.st_atime).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"    Perms:    {oct(stat.S_IMODE(s.st_mode))}"
            f"{line_info}{link_info}{dir_info}\n"
            f"    Path:     {path}"
        )

    def _count_files(self, params):
        path = expand(params.get("path", params.get("directory", "~")))
        ext  = params.get("extension", "").lstrip(".")
        if not os.path.isdir(path):
            return f"Directory not found: {path}"
        if ext:
            n = len(list(Path(path).rglob(f"*.{ext}")))
            return f"  🔢 Found {n} .{ext} file(s) in {path}"
        counts  = defaultdict(int)
        total_f = total_d = 0
        for e in Path(path).rglob("*"):
            if e.is_dir(): total_d += 1
            else:
                total_f += 1
                counts[e.suffix.lower() or "(no ext)"] += 1
        result = (f"  🔢 {path}\n"
                  f"    Files:   {total_f}  |  Folders: {total_d}\n"
                  f"    By type:\n")
        for k, v in sorted(counts.items(), key=lambda x: -x[1])[:12]:
            result += f"      {k:<18}  {v}\n"
        return result

    def _disk_usage(self, params):
        path = expand(params.get("path", "~"))
        if not os.path.exists(path):
            return f"Path not found: {path}"
        total, used, free = shutil.disk_usage(path)
        pct = used / total * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))

        breakdown = ""
        if os.path.isdir(path):
            sizes = []
            for e in os.listdir(path):
                full = os.path.join(path, e)
                try:
                    if os.path.isdir(full):
                        s = sum(f.stat().st_size for f in Path(full).rglob("*") if f.is_file())
                    else:
                        s = os.path.getsize(full)
                    sizes.append((s, e))
                except Exception:
                    pass
            sizes.sort(reverse=True)
            if sizes:
                breakdown = f"\n{_sep(40)}\n  Largest items:\n"
                for s, name in sizes[:5]:
                    breakdown += f"    {_fmt_size(s):<12}  {name}\n"

        return (f"  💾 Disk Usage\n{_sep(40)}\n"
                f"    Path:   {path}\n"
                f"    Total:  {_fmt_size(total)}\n"
                f"    Used:   {_fmt_size(used)}  ({pct:.1f}%)\n"
                f"    Free:   {_fmt_size(free)}\n"
                f"    [{bar}]"
                f"{breakdown}")

    # ── Organize ──────────────────────────────────────────────────────────────

    def _create_folder(self, params):
        path = expand(params.get("path", params.get("name", "")))
        if not path:
            return "No folder path specified."
        os.makedirs(path, exist_ok=True)
        return f"  📁 Created folder: {path}"

    def _organize(self, params):
        folder = expand(params.get("path", params.get("directory", "~/Downloads")))
        if not os.path.isdir(folder):
            return f"Directory not found: {folder}"
        type_map = {
            "Documents":    [".pdf",".doc",".docx",".txt",".odt",".rtf",".md",".pptx",".pages"],
            "Images":       [".jpg",".jpeg",".png",".gif",".bmp",".svg",".webp",".ico",".tiff",".raw",".heic"],
            "Videos":       [".mp4",".mkv",".avi",".mov",".wmv",".flv",".webm",".m4v"],
            "Audio":        [".mp3",".wav",".flac",".aac",".ogg",".m4a",".wma"],
            "Archives":     [".zip",".tar",".gz",".rar",".7z",".bz2",".xz"],
            "Code":         [".py",".js",".ts",".html",".css",".sh",".json",".xml",
                             ".c",".cpp",".java",".rb",".go",".rs",".php",".dart"],
            "Spreadsheets": [".xlsx",".xls",".csv",".ods"],
            "Executables":  [".deb",".AppImage",".run",".bin",".exe"],
        }
        counts, skipped = defaultdict(int), []
        for filename in os.listdir(folder):
            fp = os.path.join(folder, filename)
            if os.path.isdir(fp):
                continue
            ext    = os.path.splitext(filename)[1].lower()
            placed = False
            for fname, exts in type_map.items():
                if ext in exts:
                    dest = os.path.join(folder, fname)
                    os.makedirs(dest, exist_ok=True)
                    shutil.move(fp, os.path.join(dest, filename))
                    counts[fname] += 1
                    placed = True
                    break
            if not placed and ext:
                skipped.append(filename)

        if not counts:
            return "  Nothing to organize."
        total  = sum(counts.values())
        detail = "\n    ".join(f"{k:<15}  {v} file(s)" for k, v in counts.items())
        result = f"  🗂️  Organized {total} file(s) in {folder}:\n    {detail}"
        if skipped:
            result += f"\n  ⚠️  {len(skipped)} unrecognized file(s) left in place"
        return result

    # ── Archive ───────────────────────────────────────────────────────────────

    def _compress(self, params):
        source = expand(params.get("source", params.get("path", "")))
        output = params.get("output", "")
        fmt    = params.get("format", "zip").lower()
        if not os.path.exists(source):
            return f"Source not found: {source}"
        base   = os.path.basename(source.rstrip("/"))
        suffix = "tar.gz" if fmt in ("tar.gz", "tgz") else fmt
        output = expand(output) if output else os.path.join(os.getcwd(), f"{base}.{suffix}")
        if fmt == "zip":
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
                if os.path.isdir(source):
                    for root, _, files in os.walk(source):
                        for file in files:
                            full = os.path.join(root, file)
                            zf.write(full, os.path.relpath(full, os.path.dirname(source)))
                else:
                    zf.write(source, base)
        elif fmt in ("tar.gz", "tgz", "tar"):
            mode = "w:gz" if fmt in ("tar.gz", "tgz") else "w"
            with tarfile.open(output, mode) as tf:
                tf.add(source, arcname=base)
        else:
            return f"Unsupported format '{fmt}'. Use: zip, tar.gz, tar"
        return (f"  📦 Compressed: {base}\n"
                f"     Output:    {output}\n"
                f"     Size:      {_fmt_size(os.path.getsize(output))}")

    def _extract(self, params):
        source = expand(params.get("source", params.get("path", "")))
        dest   = expand(params.get("destination", params.get("output",
                        os.path.dirname(source) or os.getcwd())))
        if not os.path.exists(source):
            return f"Archive not found: {source}"
        os.makedirs(dest, exist_ok=True)
        if zipfile.is_zipfile(source):
            with zipfile.ZipFile(source) as zf:
                zf.extractall(dest)
                n = len(zf.namelist())
        elif tarfile.is_tarfile(source):
            with tarfile.open(source, "r:*") as tf:
                n = len(tf.getmembers())
                tf.extractall(dest)
        else:
            return f"Unrecognised archive format: {source}"
        return (f"  📂 Extracted: {os.path.basename(source)}\n"
                f"     Items:    {n}\n"
                f"     Dest:     {dest}")

    # ── Permissions & Ownership ───────────────────────────────────────────────

    def _chmod(self, params):
        path = expand(params.get("path", params.get("file", "")))
        mode = params.get("mode", params.get("permissions", ""))
        if not path: return "No path specified."
        if not mode: return "No mode specified. Example: mode=755"
        if not os.path.exists(path): return f"Not found: {path}"
        try:
            os.chmod(path, int(mode, 8))
            return f"  🔒 Permissions set to {mode} on: {os.path.basename(path)}"
        except Exception as e:
            return f"  ⚠️  chmod failed: {e}"

    def _chown(self, params):
        path  = expand(params.get("path", params.get("file", "")))
        owner = params.get("owner", params.get("user", ""))
        if not path:  return "No path specified."
        if not owner: return "No owner. Example: owner=neezar:neezar"
        try:
            result = subprocess.run(
                ["sudo", "chown", "-R", owner, path],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return f"  🔒 Ownership set to '{owner}' on: {path}"
            return f"  ⚠️  chown failed: {result.stderr.strip()}"
        except Exception as e:
            return f"  ⚠️  chown error: {e}"

    # ── Symlinks ──────────────────────────────────────────────────────────────

    def _symlink(self, params):
        target = expand(params.get("target", params.get("source", "")))
        link   = expand(params.get("link", params.get("destination", params.get("path", ""))))
        if not target: return "No target specified."
        if not link:   return "No link path specified."
        if not os.path.exists(target):
            return f"Target not found: {target}"
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(target, link)
        return f"  🔗 Symlink created:\n     {link} → {target}"

    # ── Open ──────────────────────────────────────────────────────────────────

    def _open_file(self, params):
        path = expand(params.get("path", params.get("file", "")))
        app  = params.get("app", params.get("with", ""))
        if not path:
            return "No file path specified."
        if not os.path.exists(path):
            return f"File not found: {path}"
        try:
            if app:
                subprocess.Popen([app, path])
                return f"  🚀 Opened '{os.path.basename(path)}' with {app}"
            subprocess.Popen(["xdg-open", path])
            return f"  🚀 Opened: {os.path.basename(path)}"
        except Exception as e:
            return f"  ⚠️  Could not open file: {e}"

    # ── New Advanced Actions ──────────────────────────────────────────────────

    def _grep_file(self, params):
        """Search for text inside files."""
        pattern   = params.get("pattern", params.get("text", params.get("query", "")))
        path      = expand(params.get("path", params.get("directory", os.getcwd())))
        recursive = params.get("recursive", True)
        ext       = params.get("extension", "")

        if not pattern:
            return "No search pattern specified."
        if not os.path.exists(path):
            return f"Path not found: {path}"

        cmd = ["grep", "-n", "--color=never", "-I"]  # -I skips binary files
        if recursive and os.path.isdir(path):
            cmd.append("-r")
        if ext:
            cmd += ["--include", f"*.{ext.lstrip('.')}"]
        cmd += [pattern, path]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            lines  = result.stdout.strip().splitlines()
            if not lines:
                return f"  🔍 No matches for '{pattern}' in {path}"
            result_text = f"  🔍 Found '{pattern}' in {len(lines)} location(s):\n"
            result_text += f"  {_sep(46)}\n"
            for line in lines[:30]:
                result_text += f"    {line}\n"
            if len(lines) > 30:
                result_text += f"    ... and {len(lines)-30} more matches"
            return result_text
        except subprocess.TimeoutExpired:
            return f"  ⚠️  Search timed out. Try a more specific path."
        except Exception as e:
            return f"  ⚠️  grep error: {e}"

    def _word_count(self, params):
        """Count lines, words, characters in a file."""
        path = expand(params.get("path", params.get("file", "")))
        if not path:
            return "No file path specified."
        if not os.path.exists(path):
            return f"File not found: {path}"
        if os.path.isdir(path):
            return "Please specify a file, not a directory."
        try:
            with open(path, "r", errors="ignore") as f:
                content = f.read()
            lines = content.count("\n")
            words = len(content.split())
            chars = len(content)
            return (
                f"  📊 {os.path.basename(path)}\n"
                f"  {_sep(40)}\n"
                f"    Lines:      {lines:,}\n"
                f"    Words:      {words:,}\n"
                f"    Characters: {chars:,}\n"
                f"    Size:       {_fmt_size(os.path.getsize(path))}"
            )
        except Exception as e:
            return f"  ⚠️  Could not count: {e}"

    def _compare_files(self, params):
        """Show diff between two files."""
        file1 = expand(params.get("file1", params.get("source", "")))
        file2 = expand(params.get("file2", params.get("destination", params.get("target", ""))))
        if not file1 or not file2:
            return "Provide file1 and file2 paths."
        if not os.path.exists(file1):
            return f"File not found: {file1}"
        if not os.path.exists(file2):
            return f"File not found: {file2}"
        try:
            result = subprocess.run(
                ["diff", "--unified=2", file1, file2],
                capture_output=True, text=True
            )
            if not result.stdout.strip():
                return f"  ✅ Files are identical: {os.path.basename(file1)} and {os.path.basename(file2)}"
            lines = result.stdout.splitlines()
            preview = "\n".join(lines[:40])
            extra   = f"\n  ... and {len(lines)-40} more lines" if len(lines) > 40 else ""
            return f"  📋 Diff: {os.path.basename(file1)} vs {os.path.basename(file2)}\n{_sep()}\n{preview}{extra}"
        except Exception as e:
            return f"  ⚠️  diff error: {e}"

    def _backup_file(self, params):
        """Create a timestamped backup of a file."""
        path = expand(params.get("path", params.get("file", params.get("source", ""))))
        dest = params.get("destination", "")
        if not path:
            return "No file path specified."
        if not os.path.exists(path):
            return f"Not found: {path}"
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(path)
        name, ext = os.path.splitext(base)
        backup_name = f"{name}_backup_{ts}{ext}"
        backup_dir  = expand(dest) if dest else os.path.dirname(path)
        backup_path = os.path.join(backup_dir, backup_name)
        os.makedirs(backup_dir, exist_ok=True)
        if os.path.isdir(path):
            shutil.copytree(path, backup_path)
        else:
            shutil.copy2(path, backup_path)
        return (
            f"  💾 Backup created:\n"
            f"     Original: {path}\n"
            f"     Backup:   {backup_path}\n"
            f"     Size:     {_fmt_size(os.path.getsize(backup_path))}"
        )

    def _watch_file(self, params):
        """Show last N lines of a file (like tail). For live watching, user needs a terminal."""
        path = expand(params.get("path", params.get("file", "")))
        n    = int(params.get("lines", 20))
        if not path:
            return "No file path specified."
        if not os.path.exists(path):
            return f"File not found: {path}"
        try:
            with open(path, "r", errors="ignore") as f:
                all_lines = f.readlines()
            tail = all_lines[-n:]
            result = f"  📄 Last {len(tail)} lines of {os.path.basename(path)}:\n{_sep()}\n"
            result += "".join(tail)
            result += f"\n{_sep()}\n  Tip: for live watching run:  tail -f {path}"
            return result
        except Exception as e:
            return f"  ⚠️  Could not read: {e}"

    def _merge_files(self, params):
        """Merge multiple text files into one output file."""
        sources = params.get("sources", params.get("files", []))
        output  = expand(params.get("output", params.get("destination", "")))

        if isinstance(sources, str):
            sources = [s.strip() for s in sources.split(",")]
        if not sources:
            return "No source files specified. Use sources=[path1, path2, ...]"
        if not output:
            return "No output path specified."

        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        merged_lines = 0
        with open(output, "w", encoding="utf-8") as out_f:
            for i, src in enumerate(sources):
                src = expand(src.strip())
                if not os.path.exists(src):
                    return f"  ⚠️  Source not found: {src}"
                with open(src, "r", errors="ignore") as in_f:
                    content = in_f.read()
                    if i > 0:
                        out_f.write("\n")
                    out_f.write(content)
                    merged_lines += content.count("\n")

        return (
            f"  📋 Merged {len(sources)} files → {output}\n"
            f"     Total lines: {merged_lines:,}\n"
            f"     Total size:  {_fmt_size(os.path.getsize(output))}"
        )

    def _set_hidden(self, params):
        """Rename a file to hide (prefix with .) or unhide it (remove . prefix)."""
        path = expand(params.get("path", params.get("file", "")))
        hide = params.get("hide", True)
        if not path:
            return "No file path specified."
        if not os.path.exists(path):
            return f"Not found: {path}"
        basename = os.path.basename(path)
        parent   = os.path.dirname(path)
        if hide:
            if basename.startswith("."):
                return f"  ℹ️  Already hidden: {basename}"
            new_name = "." + basename
        else:
            if not basename.startswith("."):
                return f"  ℹ️  Not hidden: {basename}"
            new_name = basename.lstrip(".")
        new_path = os.path.join(parent, new_name)
        os.rename(path, new_path)
        action = "Hidden" if hide else "Unhidden"
        return f"  ✏️  {action}: '{basename}' → '{new_name}'"
