"""
JARVIS - Command Validator & Safety Layer
=========================================
Rules:
  - DELETE actions require confirmation (permanent data loss protection)
  - Everything else passes through freely — sudo, system paths, all allowed
  - Path traversal (../../) is still blocked as it's likely a bug not intent
"""

import os
import re


# ── Only destructive FILE DELETION requires confirmation ────────────────────
DESTRUCTIVE_ACTIONS = {
    "delete", "delete_file", "delete_folder",
    "delete_by_type", "delete_by_extension",
    "remove", "remove_file", "remove_folder",
}

# ── Required params per action ──────────────────────────────────────────────
REQUIRED_PARAMS = {
    "move":           ["source", "destination"],
    "move_by_type":   ["extension", "source", "destination"],
    "copy":           ["source", "destination"],
    "rename":         ["source", "new_name"],
    "rename_bulk":    ["path", "mode"],
    "delete":         ["path"],
    "delete_by_type": ["path", "extension"],
    "compress":       ["source"],
    "extract":        ["source"],
    "write_file":     ["path", "content"],
    "append_file":    ["path", "content"],
    "edit_file":      ["path", "instruction"],
    "run_command":    ["command"],
    "open":           ["url"],
    "download":       ["url"],
    "send_email":     ["to", "subject", "body"],
}


class ValidationError(Exception):
    pass


class ConfirmationRequired(Exception):
    """Raised when a destructive action needs user confirmation."""
    def __init__(self, message: str, decision: dict):
        super().__init__(message)
        self.decision = decision


def validate(decision: dict, skip_confirmation: bool = False) -> dict:
    """
    Validate a decision before execution.
    Only raises for:
      - Missing required params
      - Path traversal attacks (../../)
      - Delete actions without confirmation
    Everything else (sudo, system paths, shell commands) passes freely.
    """
    action = decision.get("action", "")
    params = decision.get("params", {})

    # 1. Check required params are present
    _check_required_params(action, params)

    # 2. Block path traversal (likely a bug/injection, not intentional)
    _check_path_traversal(params)

    # 3. Expand ~ in all path params
    params = _expand_paths(params)

    # 4. Delete actions require confirmation only
    if action in DESTRUCTIVE_ACTIONS and not skip_confirmation:
        target = params.get("path", params.get("source", "the selected item"))
        raise ConfirmationRequired(
            f"  ⚠️  This will permanently delete: '{target}'\n"
            f"  Type 'yes' to confirm or anything else to cancel.",
            decision
        )

    decision["params"] = params
    return decision


def _check_required_params(action: str, params: dict):
    """Raise ValidationError if required params are missing."""
    required = REQUIRED_PARAMS.get(action, [])
    missing  = []

    # Accepted aliases per field
    aliases = {
        "path":        ["path", "file", "source", "directory", "folder"],
        "source":      ["source", "path", "file", "src"],
        "destination": ["destination", "dest", "target", "dst"],
        "content":     ["content", "text", "body", "data"],
        "command":     ["command", "cmd", "shell"],
        "to":          ["to", "recipient", "email"],
    }

    for field in required:
        accepted = aliases.get(field, [field])
        has_value = any(
            bool(params.get(a, "").strip())
            if isinstance(params.get(a), str)
            else bool(params.get(a))
            for a in accepted
        )
        if not has_value:
            missing.append(field)

    if missing:
        raise ValidationError(
            f"  Missing required info for '{action}': {', '.join(missing)}\n"
            f"  Please try again with more detail."
        )


def _check_path_traversal(params: dict):
    """Block obvious path traversal patterns (../../)."""
    path_keys = ["path", "source", "destination", "directory",
                 "folder", "file", "output", "src", "dst", "target"]
    for key in path_keys:
        val = params.get(key, "")
        if isinstance(val, str) and ".." in val:
            raise ValidationError(
                f"  Path traversal detected in '{key}': {val}\n"
                f"  Use absolute paths instead."
            )


def _expand_paths(params: dict) -> dict:
    """Expand ~ in all path-like params."""
    path_keys = ["path", "source", "destination", "directory",
                 "folder", "file", "output", "src", "dst", "target"]
    cleaned = dict(params)
    for key in path_keys:
        val = cleaned.get(key, "")
        if val and isinstance(val, str):
            cleaned[key] = os.path.abspath(os.path.expanduser(val))
    return cleaned
