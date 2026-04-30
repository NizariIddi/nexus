"""
JARVIS Plugin: Browser Automation (Puppeteer)
==============================================
Talks to a persistent browser_server.js over a TCP socket.
The browser stays open between commands.

Setup (one-time):
  sudo apt install nodejs npm chromium-browser
  cd ~/Downloads/jarvis_v2 && npm install puppeteer-core

The server starts automatically when you first use a browser command.
"""

import os
import json
import socket
import subprocess
import time
import sys
from core.plugin_base import JarvisPlugin

PORT       = 9009
HOST       = "127.0.0.1"
JARVIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_JS  = os.path.join(JARVIS_DIR, "browser_server.js")
SAVE_DIR   = os.path.expanduser("~/Downloads/jarvis_scraped")


def _send(action: str, params: dict = {}, timeout: int = 40) -> dict:
    """Send a command to the browser server and return the response."""
    cmd = json.dumps({"action": action, "params": params}) + "\n"
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout) as sock:
            sock.sendall(cmd.encode())
            response = b""
            sock.settimeout(timeout)
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                response += chunk
                if b"\n" in response:
                    break
        line = response.decode().strip().split("\n")[0]
        return json.loads(line)
    except ConnectionRefusedError:
        return {"ok": False, "error": "SERVER_NOT_RUNNING"}
    except socket.timeout:
        return {"ok": False, "error": f"Browser action timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _is_server_running() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=2):
            return True
    except Exception:
        return False


def _start_server() -> str | None:
    """Start the browser server as a background process. Returns error or None."""
    if not os.path.exists(SERVER_JS):
        return (
            f"  ⚠️  browser_server.js not found at:\n     {SERVER_JS}\n"
            f"  Make sure you extracted it to your jarvis_v2 folder."
        )

    node_modules = os.path.join(JARVIS_DIR, "node_modules", "puppeteer-core")
    if not os.path.isdir(node_modules):
        return (
            "  ⚠️  puppeteer-core not installed.\n"
            "  Run:\n\n"
            f"    cd {JARVIS_DIR}\n"
            "    npm install puppeteer-core\n"
        )

    env = os.environ.copy()
    env["NODE_PATH"] = os.path.join(JARVIS_DIR, "node_modules")

    try:
        subprocess.Popen(
            ["node", SERVER_JS],
            cwd=JARVIS_DIR, env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait for server to be ready (up to 8 seconds)
        for _ in range(16):
            time.sleep(0.5)
            if _is_server_running():
                return None
        return "  ⚠️  Browser server started but not responding. Try again in a moment."
    except FileNotFoundError:
        return (
            "  ⚠️  Node.js not found.\n"
            "  Install: sudo apt install nodejs npm"
        )
    except Exception as e:
        return f"  ⚠️  Could not start browser server: {e}"


def _ensure_server() -> str | None:
    """Make sure server is running. Returns error string or None."""
    if _is_server_running():
        return None
    print("  🚀 Starting browser server...", flush=True)
    return _start_server()


def _ok(r: dict, success_msg: str) -> str:
    if r.get("ok"):
        return success_msg
    err = r.get("error", "Unknown error")
    if err == "SERVER_NOT_RUNNING":
        return "  ⚠️  Browser server not running. Say 'go to <url>' to start it."
    return f"  ⚠️  {err}"


class BrowserAutoPlugin(JarvisPlugin):
    NAME        = "browser_auto"
    CATEGORY    = "browser_auto"
    DESCRIPTION = "Browser automation — navigate, click, fill forms, scrape data"

    ACTIONS = [
        "goto", "navigate_to", "open_page",
        "go_back", "reload", "refresh",
        "click", "click_button", "click_link",
        "type_text", "type_in", "fill_field",
        "fill_form",
        "submit_form", "submit",
        "scroll_down", "scroll_up",
        "press_key",
        "wait", "pause",
        "scrape_text", "get_text", "get_page_text",
        "scrape_links", "get_links",
        "scrape_table", "get_table",
        "scrape_images", "get_images",
        "scrape_data", "extract_data",
        "get_title", "page_title",
        "get_url", "current_url",
        "screenshot_page", "page_screenshot",
        "close_browser", "close",
        "browser_status", "status",
        "stop_browser_server",
    ]

    ACTIONS_PROMPT = """
BROWSER AUTOMATION (category: "browser_auto") — controls a persistent visible Chromium browser:
  goto            params: {"url":"https://youtube.com"}
  click           params: {"selector":"Sign In"}
  type_text       params: {"selector":"search","text":"linux tutorial"}
  fill_form       params: {"fields":{"username":"john","password":"pass"}}
  submit_form     params: {"selector":"optional button text"}
  scroll_down     params: {"amount":500}
  press_key       params: {"key":"Enter"}
  wait            params: {"seconds":2}
  scrape_text     params: {"selector":"optional CSS"}
  scrape_links    params: {"filter":"optional keyword"}
  scrape_table    params: {"index":0}
  scrape_images   params: {}
  scrape_data     params: {}
  get_title       params: {}
  get_url         params: {}
  screenshot_page params: {"filename":"optional.png"}
  go_back         params: {}
  reload          params: {}
  close_browser   params: {}
  browser_status  params: {}

  Examples:
  "go to youtube.com"       → {"category":"browser_auto","action":"goto","params":{"url":"https://youtube.com"},"message":"Opening YouTube."}
  "click Sign In"           → {"category":"browser_auto","action":"click","params":{"selector":"Sign In"},"message":"Clicking Sign In."}
  "type code tv in search"  → {"category":"browser_auto","action":"type_text","params":{"selector":"search","text":"code tv"},"message":"Typing in search bar."}
  "scrape all links"        → {"category":"browser_auto","action":"scrape_links","params":{},"message":"Scraping links."}
  "take a screenshot"       → {"category":"browser_auto","action":"screenshot_page","params":{},"message":"Taking screenshot."}"""

    def handle(self, action: str, params: dict) -> str:
        # Status and stop don't need the server running
        if action in ("browser_status", "status"):
            return self._status()
        if action == "stop_browser_server":
            return self._stop_server()

        # close_browser — stop browser but keep server
        if action in ("close_browser", "close"):
            if not _is_server_running():
                return "  ℹ️  Browser server is not running."
            r = _send("close_browser")
            return _ok(r, "  ✅ Browser closed. Server still running.")

        # All other actions — ensure server is up
        err = _ensure_server()
        if err: return err

        dispatch = {
            "goto":            self._goto,
            "navigate_to":     self._goto,
            "open_page":       self._goto,
            "go_back":         self._go_back,
            "reload":          self._reload,
            "refresh":         self._reload,
            "click":           self._click,
            "click_button":    self._click,
            "click_link":      self._click,
            "type_text":       self._type_text,
            "type_in":         self._type_text,
            "fill_field":      self._type_text,
            "fill_form":       self._fill_form,
            "submit_form":     self._submit,
            "submit":          self._submit,
            "scroll_down":     lambda p: self._scroll(p, "down"),
            "scroll_up":       lambda p: self._scroll(p, "up"),
            "press_key":       self._press_key,
            "wait":            self._wait,
            "pause":           self._wait,
            "scrape_text":     self._scrape_text,
            "get_text":        self._scrape_text,
            "get_page_text":   self._scrape_text,
            "scrape_links":    self._scrape_links,
            "get_links":       self._scrape_links,
            "scrape_table":    self._scrape_table,
            "get_table":       self._scrape_table,
            "scrape_images":   self._scrape_images,
            "get_images":      self._scrape_images,
            "scrape_data":     self._scrape_data,
            "extract_data":    self._scrape_data,
            "get_title":       self._get_title,
            "page_title":      self._get_title,
            "get_url":         self._get_url,
            "current_url":     self._get_url,
            "screenshot_page": self._screenshot,
            "page_screenshot": self._screenshot,
        }
        fn = dispatch.get(action)
        if fn: return fn(params)
        return f"  Unknown browser_auto action: '{action}'"

    # ── Actions ───────────────────────────────────────────────────────────────

    def _goto(self, params: dict) -> str:
        url = params.get("url", params.get("link", params.get("page", ""))).strip()
        if not url: return "  ⚠️  No URL specified."
        if not url.startswith(("http://", "https://")): url = "https://" + url
        r = _send("goto", {"url": url}, timeout=45)
        if r.get("ok"):
            return f"  🌐 {r.get('output', 'Navigated')}\n     Title: {r.get('title', '')}"
        return f"  ⚠️  {r.get('error')}"

    def _go_back(self, params: dict = {}) -> str:
        r = _send("go_back")
        return f"  ⬅️  {r.get('output', r.get('error', 'Done'))}"

    def _reload(self, params: dict = {}) -> str:
        r = _send("reload")
        return f"  🔄 {r.get('output', r.get('error', 'Done'))}"

    def _click(self, params: dict) -> str:
        sel = (params.get("selector") or params.get("element") or
               params.get("button") or params.get("text") or
               params.get("target") or "")
        if not sel: return "  ⚠️  No element specified."
        r = _send("click", {"selector": sel})
        return (f"  🖱️  {r['output']}" if r.get("ok")
                else f"  ⚠️  {r.get('error')}")

    def _type_text(self, params: dict) -> str:
        sel  = (params.get("selector") or params.get("field") or
                params.get("input") or params.get("element") or "")
        text = str(params.get("text", params.get("value", params.get("content", ""))))
        if not sel:  return "  ⚠️  No field specified."
        if not text: return "  ⚠️  No text specified."
        r = _send("type_text", {"selector": sel, "text": text})
        return (f"  ⌨️  {r['output']}" if r.get("ok")
                else f"  ⚠️  {r.get('error')}")

    def _fill_form(self, params: dict) -> str:
        fields = params.get("fields", params.get("data", params.get("form", {})))
        if not fields or not isinstance(fields, dict):
            return "  ⚠️  No fields. Use fields={'name':'John','email':'...'}"
        r = _send("fill_form", {"fields": fields})
        if not r.get("ok"):
            return f"  ⚠️  {r.get('error')}"
        try:
            d      = json.loads(r["output"])
            filled = d.get("filled", [])
            errors = d.get("errors", [])
            out    = f"  📝 Form filled ({len(filled)}/{len(filled)+len(errors)} fields):\n"
            for f in filled: out += f"    ✅ {f}\n"
            for e in errors: out += f"    ⚠️  {e}\n"
            return out
        except Exception:
            return "  📝 Form fill attempted."

    def _submit(self, params: dict) -> str:
        sel = params.get("selector", params.get("button", ""))
        r   = _send("submit", {"selector": sel})
        return (f"  ✅ {r['output']}" if r.get("ok")
                else f"  ⚠️  {r.get('error')}")

    def _scroll(self, params: dict, direction: str) -> str:
        amount = int(params.get("amount", params.get("pixels", 500)))
        action = "scroll_down" if direction == "down" else "scroll_up"
        r = _send(action, {"amount": amount})
        return f"  ↕️  {r.get('output', r.get('error', 'Done'))}"

    def _press_key(self, params: dict) -> str:
        key = params.get("key", params.get("keys", params.get("press", "")))
        if not key: return "  ⚠️  No key specified."
        r = _send("press_key", {"key": key})
        return f"  ⌨️  {r.get('output', r.get('error', 'Done'))}"

    def _wait(self, params: dict) -> str:
        seconds = float(params.get("seconds", params.get("time", 2)))
        r = _send("wait", {"seconds": seconds}, timeout=int(seconds) + 10)
        return f"  ⏳ {r.get('output', 'Done')}"

    def _scrape_text(self, params: dict) -> str:
        sel = params.get("selector", params.get("element", ""))
        r   = _send("scrape_text", {"selector": sel})
        if not r.get("ok"): return f"  ⚠️  {r.get('error')}"
        try:
            d = json.loads(r["output"])
            return (f"  📄 Scraped {d['count']} lines:\n  {'─'*48}\n{d['preview']}\n"
                    f"  {'─'*48}\n  💾 Saved: {d['file']}")
        except Exception:
            return "  📄 Text scraped."

    def _scrape_links(self, params: dict) -> str:
        filt = params.get("filter", params.get("keyword", ""))
        r    = _send("scrape_links", {"filter": filt})
        if not r.get("ok"): return f"  ⚠️  {r.get('error')}"
        try:
            d = json.loads(r["output"])
            return (f"  🔗 Found {d['count']} link(s):\n  {'─'*48}\n{d['preview']}\n"
                    f"  {'─'*48}\n  💾 Saved: {d['file']}")
        except Exception:
            return "  🔗 Links scraped."

    def _scrape_table(self, params: dict) -> str:
        idx = int(params.get("index", params.get("table", 0)))
        r   = _send("scrape_table", {"index": idx})
        if not r.get("ok"): return f"  ⚠️  {r.get('error')}"
        try:
            d = json.loads(r["output"])
            return (f"  📊 Table {idx} ({d['rows']} rows × {d['cols']} cols):\n"
                    f"  {'─'*48}\n{d['preview']}\n"
                    f"  {'─'*48}\n  💾 Saved: {d['file']}")
        except Exception:
            return "  📊 Table scraped."

    def _scrape_images(self, params: dict) -> str:
        r = _send("scrape_images")
        if not r.get("ok"): return f"  ⚠️  {r.get('error')}"
        try:
            d = json.loads(r["output"])
            return (f"  🖼️  Found {d['count']} image(s):\n  {'─'*48}\n{d['preview']}\n"
                    f"  {'─'*48}\n  💾 Saved: {d['file']}")
        except Exception:
            return "  🖼️  Images scraped."

    def _scrape_data(self, params: dict) -> str:
        r = _send("scrape_data")
        if not r.get("ok"): return f"  ⚠️  {r.get('error')}"
        try:
            d  = json.loads(r["output"])
            pg = d["data"]
            out = (f"  📦 Data from: {pg['url']}\n"
                   f"  Title: {pg['title']}\n  {'─'*48}\n")
            if pg.get("headings"):
                out += f"  Headings ({len(pg['headings'])}):\n"
                for h in pg["headings"][:5]:
                    out += f"    [{h['tag']}] {h['text'][:60]}\n"
            out += (f"  Links: {pg['links']}  |  "
                    f"Images: {pg['images']}  |  "
                    f"Tables: {pg['tables']}\n")
            out += f"  {'─'*48}\n  💾 Saved: {d['file']}"
            return out
        except Exception:
            return "  📦 Data extracted."

    def _get_title(self, params: dict = {}) -> str:
        r = _send("get_title")
        return (f"  📄 Title: {r.get('output', '?')}" if r.get("ok")
                else f"  ⚠️  {r.get('error')}")

    def _get_url(self, params: dict = {}) -> str:
        r = _send("get_url")
        return (f"  🌐 URL: {r.get('output', '?')}" if r.get("ok")
                else f"  ⚠️  {r.get('error')}")

    def _screenshot(self, params: dict) -> str:
        from datetime import datetime
        filename  = params.get("filename", f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        full_page = params.get("full_page", False)
        r = _send("screenshot_page", {"filename": filename, "full_page": full_page})
        return (f"  📸 Screenshot saved:\n     {r.get('output', '')}" if r.get("ok")
                else f"  ⚠️  {r.get('error')}")

    def _status(self) -> str:
        if not _is_server_running():
            return (
                "  🔴 Browser server is not running.\n"
                "  Say 'go to <url>' to start it automatically."
            )
        r = _send("status")
        if not r.get("ok"):
            return f"  ⚠️  {r.get('error')}"
        try:
            d = json.loads(r["output"])
            if d.get("running"):
                return (f"  🟢 Browser is open\n"
                        f"     URL:   {d.get('url', '?')}\n"
                        f"     Title: {d.get('title', '?')}")
            return "  🟡 Server running but browser is closed. Say 'go to <url>' to open."
        except Exception:
            return "  🟡 Server is running."

    def _stop_server(self) -> str:
        if not _is_server_running():
            return "  ℹ️  Browser server is not running."
        _send("shutdown")
        return "  ✅ Browser server stopped."
