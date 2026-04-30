"""
JARVIS Plugin Registry
======================
Auto-discovers all plugins in the plugins/ directory.
No manual registration needed — just drop a file in plugins/.
"""

import os
import importlib
import inspect
from core.plugin_base import JarvisPlugin


class PluginRegistry:
    def __init__(self):
        self._plugins:    dict[str, JarvisPlugin] = {}   # category → plugin
        self._action_map: dict[str, JarvisPlugin] = {}   # action   → plugin

    def discover(self, plugins_dir: str = "plugins"):
        """Scan plugins/ and auto-load all JarvisPlugin subclasses."""
        if not os.path.isdir(plugins_dir):
            return

        for filename in sorted(os.listdir(plugins_dir)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            module_name = f"plugins.{filename[:-3]}"
            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                print(f"\n  ⚠️  Could not load plugin '{filename}': {e}")
                continue

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, JarvisPlugin)
                        and obj is not JarvisPlugin
                        and obj.NAME):
                    instance = obj()
                    self._plugins[obj.CATEGORY] = instance
                    for action in obj.ACTIONS:
                        self._action_map[action] = instance

    def inject_ai(self, client, model: str):
        """Pass AI client to every plugin that may need it."""
        for plugin in self._plugins.values():
            plugin.set_ai(client, model)

    def route(self, category: str, action: str, params: dict) -> str:
        """Find the right plugin and execute the action."""
        plugin = self._action_map.get(action) or self._plugins.get(category)

        if not plugin:
            return (
                f"  No plugin for category='{category}', action='{action}'.\n"
                f"  Available: {', '.join(self._plugins.keys())}"
            )
        try:
            return plugin.handle(action, params)
        except Exception as e:
            return f"  Plugin '{plugin.NAME}' error on '{action}': {e}"

    def build_prompt(self) -> str:
        """
        Auto-build the actions section of the system prompt from all loaded plugins.
        Each plugin owns its ACTIONS_PROMPT — no manual edits to main.py needed.
        """
        lines = []
        for plugin in self._plugins.values():
            if plugin.ACTIONS_PROMPT:
                lines.append(plugin.ACTIONS_PROMPT.strip())
        return "\n".join(lines)

    def list_plugins(self) -> str:
        """Pretty-print loaded plugins for the 'plugins' command."""
        if not self._plugins:
            return "  No plugins loaded."

        sep   = "─" * 52
        lines = [f"\n  ┌{sep}┐",
                 f"  │  {'Loaded Plugins':<50}│",
                 f"  ├{sep}┤"]

        for cat, p in self._plugins.items():
            lines.append(f"  │  [{cat:<10}]  {p.NAME:<12}  {p.DESCRIPTION:<18}│")
            action_preview = ", ".join(p.ACTIONS[:5])
            if len(p.ACTIONS) > 5:
                action_preview += f" +{len(p.ACTIONS)-5} more"
            lines.append(f"  │    Actions: {action_preview:<38}│")
            lines.append(f"  ├{sep}┤")

        lines[-1] = f"  └{sep}┘"
        return "\n".join(lines)
