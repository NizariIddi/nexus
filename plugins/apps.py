"""
JARVIS Plugin: App Launcher & Window Manager
"""

import subprocess
import shutil
import time
import os
from core.plugin_base import JarvisPlugin


class AppsPlugin(JarvisPlugin):
    NAME        = "apps"
    CATEGORY    = "app"
    DESCRIPTION = "Launch apps, manage windows, run shell commands, take screenshots"
    ACTIONS     = [
        "launch", "open", "start",
        "close", "kill", "stop",
        "list_windows", "list",
        "focus", "switch",
        "minimize", "maximize",
        "run_command", "command", "shell",
        "install_package", "install",
        "screenshot",
    ]

    ACTIONS_PROMPT = """
APP ACTIONS (category: "app"):
  launch          params: {"app":"firefox"}
  close           params: {"app":"firefox"}
  list_windows    params: {}
  focus           params: {"app":"..."}
  minimize        params: {"app":"..."}
  maximize        params: {"app":"..."}
  run_command     params: {"command":"ls -la"}   ← any shell command
  install_package params: {"package":"nmap"}     ← opens terminal and installs
  screenshot      params: {"filename":"optional.png"}

  IMPORTANT: When user says "install X" → always use action=install_package with params={"package":"X"}
  Never use run_command for install requests."""

    KEYWORD_MAP = [
        (["terminal", "console", "command line", "bash shell"], "terminal"),
        (["trash", "recycle bin"],                               "trash"),
        (["firefox", "mozilla"],                                 "firefox"),
        (["chrome", "chromium"],                                 "google-chrome"),
        (["vlc", "media player", "video player"],               "vlc"),
        (["files", "file manager", "nautilus"],                  "nautilus"),
        (["text editor", "gedit", "notepad", "mousepad"],       "gedit"),
        (["calculator", "calc"],                                 "gnome-calculator"),
        (["app center", "software center", "gnome software"],   "snap-store"),
        (["vscode", "vs code", "visual studio"],                "code"),
        (["spotify"],                                            "spotify"),
        (["discord"],                                            "discord"),
        (["slack"],                                              "slack"),
        (["zoom"],                                               "zoom"),
        (["rhythmbox", "music player"],                          "rhythmbox"),
        (["gimp", "image editor"],                               "gimp"),
        (["libreoffice"],                                        "libreoffice"),
        (["thunderbird", "mail"],                                "thunderbird"),
        (["brave"],                                              "brave-browser"),
    ]

    def handle(self, action: str, params: dict) -> str:
        if action in ("launch", "open", "start"):
            return self._launch(params)
        elif action in ("close", "kill", "stop"):
            return self._close(params)
        elif action in ("list_windows", "list"):
            return self._list_windows()
        elif action in ("focus", "switch"):
            return self._focus(params)
        elif action == "minimize":
            return self._minimize(params)
        elif action == "maximize":
            return self._maximize(params)
        elif action in ("run_command", "command", "shell"):
            return self._run_command(params)
        elif action in ("install_package", "install"):
            return self._install_package(params)
        elif action == "screenshot":
            return self._screenshot(params)
        return f"Unknown app action: '{action}'"

    def _get_name(self, params: dict) -> str:
        for key in ("app", "name", "application", "program", "software", "process", "target"):
            val = params.get(key, "")
            if val: return str(val).lower().strip()
        for val in params.values():
            if isinstance(val, str) and val.strip():
                return val.lower().strip()
        return ""

    def _fuzzy_match(self, app: str) -> str | None:
        for keywords, cmd in self.KEYWORD_MAP:
            for kw in keywords:
                if kw in app: return cmd
        return None

    def _find_terminal(self) -> str | None:
        """Return the first available terminal emulator command."""
        for term in ["gnome-terminal", "ptyxis", "konsole", "xfce4-terminal",
                     "mate-terminal", "tilix", "alacritty", "kitty",
                     "lxterminal", "terminator", "xterm"]:
            if shutil.which(term):
                return term
        if shutil.which("x-terminal-emulator"):
            return "x-terminal-emulator"
        return None

    def _open_terminal_with_command(self, cmd: str) -> str:
        """
        Open the available terminal emulator and run cmd inside it.
        The terminal stays open after the command finishes so the user can see output.
        """
        term = self._find_terminal()
        if not term:
            return (
                "  ⚠️  No terminal emulator found.\n"
                "  Install one first: sudo apt install gnome-terminal\n"
                f"  Then run manually: {cmd}"
            )

        # Build the shell snippet: run cmd, print separator, then keep shell open
        shell_snippet = (
            f"echo ''; "
            f"echo '  ── Running: {cmd} ──'; "
            f"echo ''; "
            f"{cmd}; "
            f"echo ''; "
            f"echo '  ── Done. Press Enter to close ──'; "
            f"read"
        )

        # Each terminal has a different flag for running a command
        try:
            if term in ("gnome-terminal", "mate-terminal"):
                subprocess.Popen([term, "--", "bash", "-c", shell_snippet])
            elif term == "ptyxis":
                subprocess.Popen([term, "--", "bash", "-c", shell_snippet])
            elif term in ("konsole",):
                subprocess.Popen([term, "-e", "bash", "-c", shell_snippet])
            elif term in ("xfce4-terminal",):
                subprocess.Popen([term, "--command", f"bash -c '{shell_snippet}'"])
            elif term in ("tilix",):
                subprocess.Popen([term, "-e", f"bash -c '{shell_snippet}'"])
            elif term in ("alacritty",):
                subprocess.Popen([term, "-e", "bash", "-c", shell_snippet])
            elif term in ("kitty",):
                subprocess.Popen([term, "bash", "-c", shell_snippet])
            elif term in ("xterm", "lxterminal", "terminator", "x-terminal-emulator"):
                subprocess.Popen([term, "-e", f"bash -c '{shell_snippet}'"])
            else:
                subprocess.Popen([term, "-e", "bash", "-c", shell_snippet])
            return term
        except Exception as e:
            return f"error:{e}"

    def _install_package(self, params: dict) -> str:
        """
        Install a package by opening a terminal and running the install command inside it.
        Supports apt, pip, npm, snap based on what the user asks.
        """
        package  = params.get("package", params.get("name", params.get("app", ""))).strip()
        manager  = params.get("manager", "").lower().strip()  # optional: pip, npm, snap

        if not package:
            return "  ⚠️  No package name specified."

        # Determine install command
        if manager == "pip" or params.get("pip"):
            cmd = f"pip3 install {package}"
        elif manager == "npm" or params.get("npm"):
            cmd = f"npm install -g {package}"
        elif manager == "snap" or params.get("snap"):
            cmd = f"sudo snap install {package}"
        elif manager == "pip3":
            cmd = f"pip3 install {package}"
        else:
            # Default: apt (most common on Ubuntu/Debian)
            cmd = f"sudo apt install -y {package}"

        result = self._open_terminal_with_command(cmd)

        if result.startswith("error:"):
            return (
                f"  ⚠️  Could not open terminal: {result[6:]}\n"
                f"  Run manually in your terminal:\n\n    {cmd}"
            )

        return (
            f"  📦 Installing '{package}' via {result}\n"
            f"  {'─'*48}\n"
            f"  Command: {cmd}\n"
            f"  A terminal window has opened — watch it for progress.\n"
            f"  The terminal will stay open so you can see the result."
        )

    def _launch(self, params: dict) -> str:
        app = self._get_name(params)
        url = params.get("url", params.get("link", ""))
        if not app: return f"  ⚠️  No app specified. (params: {params})"
        matched = self._fuzzy_match(app)

        if matched == "terminal" or "terminal" in app or "console" in app:
            term = self._find_terminal()
            if term:
                subprocess.Popen([term])
                return f"  🚀 Opened terminal ({term})"
            return "  ⚠️  No terminal emulator found.\n     Install: sudo apt install gnome-terminal"

        if matched == "trash" or "trash" in app:
            for fm in ["nautilus", "thunar", "nemo", "dolphin", "pcmanfm"]:
                if shutil.which(fm):
                    subprocess.Popen([fm, "trash:///"])
                    return f"  🗑️  Opened Trash in {fm}"
            subprocess.Popen(["xdg-open", "trash:///"])
            return "  🗑️  Opened Trash"

        cmd = matched if matched else app.split()[0]
        if url and cmd in ("firefox", "google-chrome", "chromium", "brave-browser"):
            subprocess.Popen([cmd, url])
            return f"  🚀 Opened {cmd} at {url}"

        if shutil.which(cmd):
            subprocess.Popen([cmd])
            time.sleep(0.5)
            return f"  🚀 Launched: {cmd}"

        return (f"  ⚠️  '{cmd}' not found.\n"
                f"     Try: sudo apt install {cmd}")

    def _close(self, params: dict) -> str:
        app = self._get_name(params)
        if not app: return "No app specified."
        result = subprocess.run(["pkill", "-f", app], capture_output=True, text=True)
        return (f"  ✅ Closed: '{app}'" if result.returncode == 0
                else f"  ⚠️  Not running: '{app}'")

    def _list_windows(self) -> str:
        if not shutil.which("wmctrl"):
            return "  ⚠️  wmctrl not installed.\n     Run: sudo apt install wmctrl"
        result = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True)
        lines  = [l for l in result.stdout.strip().split("\n") if l]
        if not lines: return "  No open windows."
        output = f"  🪟 Open windows ({len(lines)}):\n"
        for line in lines:
            parts = line.split(None, 3)
            if len(parts) >= 4:
                output += f"    • {parts[3]}\n"
        return output

    def _focus(self, params: dict) -> str:
        name = self._get_name(params)
        if not shutil.which("wmctrl"): return "  ⚠️  wmctrl not installed."
        result = subprocess.run(["wmctrl", "-a", name], capture_output=True, text=True)
        return (f"  ✅ Focused: '{name}'" if result.returncode == 0
                else f"  ⚠️  Window not found: '{name}'")

    def _minimize(self, params: dict) -> str:
        name = self._get_name(params)
        if not shutil.which("xdotool"): return "  ⚠️  xdotool not installed."
        result = subprocess.run(["xdotool", "search", "--name", name, "windowminimize"],
                                capture_output=True, text=True)
        return (f"  ✅ Minimized: '{name}'" if result.returncode == 0
                else f"  ⚠️  Could not minimize: '{name}'")

    def _maximize(self, params: dict) -> str:
        name = self._get_name(params)
        if not shutil.which("xdotool"): return "  ⚠️  xdotool not installed."
        result = subprocess.run(
            ["xdotool", "search", "--name", name, "windowactivate",
             "--sync", "key", "--window", "%1", "super+Up"],
            capture_output=True, text=True)
        return (f"  ✅ Maximized: '{name}'" if result.returncode == 0
                else f"  ⚠️  Could not maximize: '{name}'")

    def _run_command(self, params: dict) -> str:
        cmd = params.get("command", params.get("cmd", params.get("shell", "")))
        if not cmd: return "No command specified."

        # Intercept install commands — redirect to terminal
        install_keywords = ("apt install", "apt-get install", "pip install", "pip3 install",
                            "npm install", "snap install", "dnf install", "yum install",
                            "brew install")
        if any(kw in cmd for kw in install_keywords):
            result = self._open_terminal_with_command(cmd)
            if result.startswith("error:"):
                return (f"  📦 Run this in your terminal:\n\n    {cmd}")
            return (
                f"  📦 Install command opened in terminal ({result})\n"
                f"  {'─'*48}\n"
                f"  Command: {cmd}\n"
                f"  Watch the terminal window for progress."
            )

        # Long-running streaming commands — redirect to terminal
        streaming_keywords = ("pm2 logs", "tail -f", "journalctl -f",
                              "watch ", "top", "htop", "ping ")
        if any(kw in cmd for kw in streaming_keywords):
            result = self._open_terminal_with_command(cmd)
            if not result.startswith("error:"):
                return (
                    f"  🖥️  Running in terminal ({result}):\n"
                    f"  {'─'*48}\n"
                    f"  {cmd}"
                )

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60
            )
            output = result.stdout.strip() or result.stderr.strip() or "(no output)"
            rc_tag = "" if result.returncode == 0 else f"  [exit {result.returncode}]\n"
            return f"  $ {cmd}\n  {'─'*48}\n{rc_tag}{output}"
        except subprocess.TimeoutExpired:
            return (f"  ⚠️  Command timed out after 60s.\n"
                    f"  Run it in a terminal instead:\n\n    {cmd}")

    def _screenshot(self, params: dict) -> str:
        from datetime import datetime
        filename  = params.get("filename",
                    f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        save_path = os.path.expanduser(f"~/Pictures/{filename}")
        os.makedirs(os.path.expanduser("~/Pictures"), exist_ok=True)
        for tool in ["scrot", "gnome-screenshot"]:
            if shutil.which(tool):
                if tool == "scrot":
                    subprocess.run([tool, save_path])
                else:
                    subprocess.run([tool, "-f", save_path])
                return f"  📸 Screenshot saved: {save_path}"
        return "  ⚠️  No screenshot tool found.\n     Install: sudo apt install scrot"
