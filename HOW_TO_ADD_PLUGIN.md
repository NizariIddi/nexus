# How to Add a New Feature to JARVIS

Adding a new feature takes **one step** — create a file in `plugins/`.
Zero changes to `main.py` needed, ever.

---

## Step 1 — Create `plugins/yourplugin.py`

```python
from core.plugin_base import JarvisPlugin
import subprocess

class SystemPlugin(JarvisPlugin):
    NAME        = "system"
    CATEGORY    = "system"        # must match what AI sends as "category"
    DESCRIPTION = "CPU, RAM, uptime, processes"
    ACTIONS     = [
        "cpu_usage", "ram_usage", "uptime",
        "list_processes", "kill_process",
    ]

    # This gets injected into the AI system prompt automatically.
    # Write it clearly — the AI reads this to know what JSON to send.
    ACTIONS_PROMPT = """
SYSTEM ACTIONS (category: "system"):
  cpu_usage      params: {}
  ram_usage      params: {}
  uptime         params: {}
  list_processes params: {}
  kill_process   params: {"process":"firefox"}"""

    def handle(self, action: str, params: dict) -> str:
        if action == "cpu_usage":
            return self._cpu()
        elif action == "ram_usage":
            return self._ram()
        elif action == "uptime":
            result = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
            return f"  ⏱️  Uptime: {result.stdout.strip()}"
        elif action == "kill_process":
            name = params.get("process", "")
            subprocess.run(["pkill", "-f", name])
            return f"  ✅ Killed: {name}"
        return f"Unknown action: {action}"

    def _cpu(self) -> str:
        result = subprocess.run(["top", "-bn1"], capture_output=True, text=True)
        for line in result.stdout.split("\n"):
            if "Cpu(s)" in line:
                return f"  🖥️  CPU: {line.strip()}"
        return "Could not get CPU usage."

    def _ram(self) -> str:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True)
        return f"  🧠 Memory:\n{result.stdout}"
```

## Done. That's it.

The plugin auto-loads on next run. The `ACTIONS_PROMPT` is automatically
added to the AI's system prompt — the AI will now understand your new category.

---

## Plugin Rules

| Rule | Why |
|------|-----|
| `NAME` must be unique | Registry key |
| `CATEGORY` matches AI's `"category"` field | Routing |
| `ACTIONS` lists every action string you handle | Action-level routing |
| `ACTIONS_PROMPT` describes your plugin to the AI | Auto system prompt |
| `handle()` must return a string | Output to user |
| Use `self.ai_client` / `self.ai_model` if you need AI | Already injected |
| Raise exceptions freely — registry catches them | Error safety |

---

## Validator Integration (optional)

If your plugin has **destructive actions** (data loss possible), add to `core/validator.py`:

```python
DESTRUCTIVE_ACTIONS = {
    ...,
    "kill_process",   # user must type 'yes' to confirm
}
```

If your action requires specific params, add to `REQUIRED_PARAMS`:

```python
REQUIRED_PARAMS = {
    ...,
    "kill_process": ["process"],
}
```
