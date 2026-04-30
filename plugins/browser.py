"""
JARVIS Plugin: Web Browser & Scraper
"""

import subprocess
import shutil
import urllib.request
import urllib.parse
import re
import os
from core.plugin_base import JarvisPlugin


class BrowserPlugin(JarvisPlugin):
    NAME        = "browser"
    CATEGORY    = "browser"
    DESCRIPTION = "Open URLs, search the web, fetch page content, download files"
    ACTIONS     = [
        "open", "open_url", "navigate", "goto",
        "search", "google", "web_search",
        "fetch", "scrape", "get_content",
        "download", "download_file",
    ]

    ACTIONS_PROMPT = """
BROWSER ACTIONS (category: "browser"):
  open      params: {"url":"https://..."}
  search    params: {"query":"...","engine":"google|duckduckgo|bing|youtube"}
  fetch     params: {"url":"https://..."}
  download  params: {"url":"https://...","destination":"~/Downloads"}"""

    def handle(self, action: str, params: dict) -> str:
        if action in ("open", "open_url", "navigate", "goto"):
            return self._open_url(params)
        elif action in ("search", "google", "web_search"):
            return self._search(params)
        elif action in ("fetch", "scrape", "get_content"):
            return self._fetch(params)
        elif action in ("download", "download_file"):
            return self._download(params)
        return f"Unknown browser action: '{action}'"

    def _get_browser(self):
        for b in ["firefox","google-chrome","chromium","chromium-browser","brave-browser"]:
            if shutil.which(b): return b
        return None

    def _open_url(self, params: dict) -> str:
        url = params.get("url", params.get("link", "")).strip()
        if not url: return "No URL specified."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        browser = self._get_browser()
        if browser:
            subprocess.Popen([browser, url])
            return f"  🌐 Opened {url}\n     Browser: {browser}"
        subprocess.Popen(["xdg-open", url])
        return f"  🌐 Opened {url}"

    def _search(self, params: dict) -> str:
        query  = params.get("query", params.get("search", params.get("q", ""))).strip()
        engine = params.get("engine", "google").lower()
        if not query: return "No search query provided."
        engines = {
            "google":     "https://www.google.com/search?q=",
            "duckduckgo": "https://duckduckgo.com/?q=",
            "bing":       "https://www.bing.com/search?q=",
            "youtube":    "https://www.youtube.com/results?search_query=",
        }
        url     = engines.get(engine, engines["google"]) + urllib.parse.quote_plus(query)
        browser = self._get_browser()
        subprocess.Popen([browser or "xdg-open", url])
        return f"  🔍 Searching {engine} for: '{query}'"

    def _fetch(self, params: dict) -> str:
        url = params.get("url", params.get("link", "")).strip()
        if not url: return "No URL specified."
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>",  "", text,  flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            preview = text[:1500] + ("..." if len(text) > 1500 else "")
            return f"  🌐 Content from {url}:\n  {'─'*48}\n{preview}"
        except Exception as e:
            return f"  ⚠️  Failed to fetch {url}:\n     {e}"

    def _download(self, params: dict) -> str:
        url  = params.get("url", params.get("link", "")).strip()
        dest = os.path.expanduser(params.get("destination", params.get("path", "~/Downloads")))
        if not url: return "No URL specified."
        filename = url.split("/")[-1].split("?")[0] or "downloaded_file"
        if os.path.isdir(dest):
            dest = os.path.join(dest, filename)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
            return (f"  ⬇️  Downloaded: {filename}\n"
                    f"     Saved to:   {dest}")
        except Exception as e:
            return f"  ⚠️  Download failed:\n     {e}"
