"""
JARVIS Plugin Base Class
========================
Every feature module subclasses JarvisPlugin.
The registry auto-discovers and loads all plugins — no changes to main.py needed.

To add a new plugin:
  1. Create plugins/yourplugin.py
  2. Subclass JarvisPlugin
  3. Fill in NAME, CATEGORY, DESCRIPTION, ACTIONS, ACTIONS_PROMPT
  4. Implement handle(action, params) -> str
  Done. It auto-loads on next run.
"""

from abc import ABC, abstractmethod


class JarvisPlugin(ABC):
    """
    Base class for all JARVIS plugins.

    Required class attributes:
      NAME          : str  — unique plugin identifier (e.g. "files")
      CATEGORY      : str  — matches the AI's "category" field (e.g. "file")
      DESCRIPTION   : str  — one-line description shown in 'plugins' command
      ACTIONS       : list — all action strings this plugin handles
      ACTIONS_PROMPT: str  — injected into system prompt so AI knows what to send
                             Use clear, compact format the model can follow.
    """

    NAME:           str  = ""
    CATEGORY:       str  = ""
    DESCRIPTION:    str  = ""
    ACTIONS:        list = []
    ACTIONS_PROMPT: str  = ""   # ← each plugin owns its own prompt fragment

    # AI client injected by registry — available as self.ai_client / self.ai_model
    ai_client = None
    ai_model:  str = ""

    def set_ai(self, client, model: str):
        self.ai_client = client
        self.ai_model  = model

    @abstractmethod
    def handle(self, action: str, params: dict) -> str:
        """Execute an action and return a human-readable result string."""
        ...

    def can_handle(self, action: str) -> bool:
        return action in self.ACTIONS
