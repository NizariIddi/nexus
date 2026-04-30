#!/usr/bin/env python3
"""
JARVIS - Linux Automation Assistant
=====================================
Architecture:
  main.py  →  validator  →  registry  →  plugin
  (AI)         (safety)     (routing)   (execution)
"""

import os
import json
import sys
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

from core.validator import validate, ValidationError, ConfirmationRequired
from core.registry  import PluginRegistry

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
# AI Provider — set in .env
# ZAI_MODEL options (Z.AI):
#   glm-4.5-flash  ← fast, free tier
#   glm-4.7        ← smarter, recommended
#   glm-4-plus     ← most capable
# Fallback to OpenRouter if ZAI_API_KEY not set
_zai_key        = os.getenv("ZAI_API_KEY", "")
_openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

if _zai_key:
    _api_key  = _zai_key
    _base_url = "https://api.z.ai/api/paas/v4"
    _default_model = "glm-4.5-flash"
else:
    _api_key  = _openrouter_key or os.getenv("GROQ_API_KEY", "")
    _base_url = "https://openrouter.ai/api/v1"
    _default_model = "mistralai/mistral-7b-instruct:free"

GROQ_MODEL = os.getenv("ZAI_MODEL",
             os.getenv("OPENROUTER_MODEL",
             os.getenv("GROQ_MODEL", _default_model)))
DEBUG      = os.getenv("JARVIS_DEBUG", "").lower() in ("1", "true", "yes")

# ── State ─────────────────────────────────────────────────────────────────────
cwd  = os.getcwd()
HOME = os.path.expanduser("~")

# ── Setup — Z.AI / OpenRouter both use OpenAI-compatible API ──────────────────
client = OpenAI(
    api_key=_api_key,
    base_url=_base_url,
)
registry = PluginRegistry()
registry.discover("plugins")
registry.inject_ai(client, GROQ_MODEL)

conversation_history: list = []


# ── System Prompt ─────────────────────────────────────────────────────────────

def get_system_prompt() -> str:
    plugin_actions = registry.build_prompt()
    return (
        f"You are JARVIS, a Linux automation assistant.\n"
        f"CWD: {cwd} | HOME: {HOME}\n"
        f"\n"
        f"RULES:\n"
        f"  - Always use full absolute paths. Never use $HOME or $USER — use {HOME}\n"
        f"  - 'here', 'this folder', 'current dir' all mean: {cwd}\n"
        f"  - To navigate: action=change_dir\n"
        f"  - To edit file content: action=edit_file with 'instruction'\n"
        f"  - To create a new file: action=write_file\n"
        f"  - If the user refers to a file/path mentioned earlier in conversation, reuse that exact path\n"
        f"  - 'install X' or 'install package X' → always use category=app, action=install_package, params={{\"package\":\"X\"}}\n"
        f"\n"
        f"RESPONSE FORMAT — always return a JSON array, never empty:\n"
        f'  [{{"category":"...","action":"...","params":{{}},"message":"..."}}]\n'
        f"\n"
        f"  Single:  [{{"
        f'"category":"file","action":"list_files","params":{{"path":"{cwd}"}},'
        f'"message":"Listing files."'
        f"}}]\n"
        f"  Multi:   [{{"
        f'"category":"file","action":"change_dir","params":{{"path":"/x"}},'
        f'"message":"Navigating."'
        f"}},{{"
        f'"category":"file","action":"list_files","params":{{"path":"/x"}},'
        f'"message":"Listing files."'
        f"}}]\n"
        f"  Chat:    [{{"
        f'"category":"chat","action":"answer","params":{{}},'
        f'"message":"Hello! How can I help you today?"'
        f"}}]\n"
        f"\n"
        f"NEVER return an empty array. For greetings/questions use category=chat.\n"
        f"\n"
        f"{plugin_actions}"
    )


# ── AI ────────────────────────────────────────────────────────────────────────

def get_ai_decisions(user_input: str) -> list[dict]:
    """Call AI and return a list of action decisions (supports multi-action)."""
    conversation_history.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "system", "content": get_system_prompt()}]
                 + conversation_history,
        temperature=0.2,
        max_tokens=800,
    )
    reply = response.choices[0].message.content.strip()
    conversation_history.append({"role": "assistant", "content": reply})

    # Strip markdown fences
    if reply.startswith("```"):
        parts = reply.split("```")
        reply = parts[1] if len(parts) > 1 else reply
        if reply.startswith("json"):
            reply = reply[4:]
    reply = reply.strip()

    # Try clean JSON parse first
    try:
        parsed = json.loads(reply)
        if isinstance(parsed, list):
            return parsed if parsed else _chat_fallback(reply)
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    # Fallback: extract JSON objects from raw string (handles two objects concatenated)
    decisions = []
    depth, start = 0, None
    for i, ch in enumerate(reply):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    obj = json.loads(reply[start:i + 1])
                    decisions.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None

    return decisions if decisions else _chat_fallback(reply)


def _chat_fallback(message: str) -> list[dict]:
    return [{"category": "chat", "action": "answer", "params": {}, "message": message}]


# ── Execution ─────────────────────────────────────────────────────────────────

def execute(decision: dict) -> str:
    global cwd
    category = decision.get("category", "chat")
    action   = decision.get("action", "")
    params   = decision.get("params", {})

    if category == "file" and action == "change_dir":
        target = os.path.abspath(os.path.expanduser(params.get("path", cwd)))
        if os.path.isdir(target):
            cwd = target
            os.chdir(cwd)
            return f"  📂 Now in: {cwd}"
        return f"  ⚠️  Directory not found: {target}"

    # Bug 2 fix — chat category returns the message to the user
    if category == "chat":
        return ""   # message already printed by caller

    return registry.route(category, action, params)


def route_with_validation(decision: dict, confirmed: bool = False):
    try:
        safe_decision = validate(decision, skip_confirmation=confirmed)
        return execute(safe_decision)
    except ValidationError as e:
        return f"  ⚠️  {e}"
    except ConfirmationRequired as e:
        return str(e), e.decision
    except Exception as e:
        return f"  ❌ Unexpected error: {e}"


# ── Logging ───────────────────────────────────────────────────────────────────

def log(user_input: str, result: str):
    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "logs", "history.log"
    )
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"[{ts}] USER:  {user_input}\n")
        f.write(f"[{ts}] JARVIS: {result}\n\n")


# ── UI Helpers ────────────────────────────────────────────────────────────────

W = 54


def _box(lines: list[str]) -> str:
    inner = W - 2
    top   = f"  ╔{'═' * inner}╗"
    bot   = f"  ╚{'═' * inner}╝"
    rows  = [f"  ║  {l:<{inner - 2}}║" for l in lines]
    return "\n".join([top] + rows + [bot])


def _divider():
    print(f"  {'─' * W}")


BANNER = _box([
    "  J A R V I S  —  Linux Edition",
    "",
    "  Your Personal Automation Assistant",
])

HELP_TEXT = (
    f"\n  {'─' * W}\n"
    f"  Type commands in plain English\n"
    f"  'plugins'  list loaded features\n"
    f"  'history'  show recent log\n"
    f"  'clear'    clear the screen\n"
    f"  'pwd'      current directory\n"
    f"  'debug'    toggle debug mode\n"
    f"  'exit'     quit\n"
    f"  {'─' * W}"
)


# ── Built-in Commands ─────────────────────────────────────────────────────────

def handle_builtin(cmd: str) -> bool:
    c = cmd.lower().strip()

    if c in ("exit", "quit", "bye"):
        print(f"\n  {'─' * W}\n  👋 Goodbye!\n  {'─' * W}\n")
        sys.exit(0)

    if c == "history":
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "logs", "history.log"
        )
        print(f"\n  {'─' * W}  HISTORY  {'─' * W}")
        if os.path.exists(log_path):
            with open(log_path) as f:
                lines = f.readlines()[-30:]
            print("".join(lines))
        else:
            print("  No history yet.")
        return True

    if c == "clear":
        os.system("clear")
        return True

    if c in ("pwd", "where am i", "current directory"):
        print(f"\n  📂 {cwd}")
        return True

    if c in ("plugins", "help"):
        print(registry.list_plugins())
        print(HELP_TEXT)
        return True

    if c == "debug":
        global DEBUG
        DEBUG = not DEBUG
        state = "ON  🔍" if DEBUG else "OFF"
        print(f"\n  Debug mode: {state}")
        return True

    return False


# ── Main Loop ─────────────────────────────────────────────────────────────────

def main():
    print(f"\n{BANNER}")
    print(f"\n  Model:    {GROQ_MODEL}")
    print(f"  Plugins:  {len(registry._plugins)} loaded — type 'plugins' to list")
    print(f"  Location: {cwd}")
    print(HELP_TEXT)

    pending_confirmation: dict | None = None

    while True:
        try:
            folder     = os.path.basename(cwd) or cwd
            user_input = input(f"\n  🧑  [{folder}] › ").strip()

            if not user_input:
                continue

            # ── Confirmation flow ──────────────────────────────────────────
            if pending_confirmation is not None:
                if user_input.lower() in ("yes", "y", "confirm"):
                    result = route_with_validation(pending_confirmation, confirmed=True)
                    pending_confirmation = None
                    if result:
                        _divider()
                        print(result)
                        _divider()
                    log("(confirmed)", str(result))
                else:
                    pending_confirmation = None
                    print(f"\n  ❌ Cancelled.")
                continue

            # ── Built-ins ──────────────────────────────────────────────────
            if handle_builtin(user_input):
                continue

            # ── AI ─────────────────────────────────────────────────────────
            print(f"\n  ⚙️   Thinking...", end="", flush=True)
            decisions = get_ai_decisions(user_input)
            print(f"\r  {' ' * 30}\r", end="", flush=True)

            if not decisions:
                print("  🤖  (no response)")
                continue

            if DEBUG:
                print(f"  🔍  {json.dumps(decisions)}")

            # ── Execute each action in sequence ────────────────────────────
            all_results = []
            for decision in decisions:
                msg      = decision.get("message", "")
                category = decision.get("category", "")

                # Always print the AI's message
                print(f"  🤖  {msg}")

                # Chat — message is the response, nothing to execute
                if category == "chat":
                    log(user_input, msg)
                    continue

                outcome = route_with_validation(decision)

                # Delete confirmation needed — pause sequence
                if isinstance(outcome, tuple):
                    confirm_msg, pending_decision = outcome
                    pending_confirmation = pending_decision
                    _divider()
                    print(confirm_msg)
                    _divider()
                    break

                if outcome:
                    _divider()
                    print(outcome)
                    _divider()
                    all_results.append(str(outcome))

            if all_results:
                log(user_input, " | ".join(all_results))

        except KeyboardInterrupt:
            print(f"\n\n  {'─' * W}\n  👋 Goodbye!\n  {'─' * W}\n")
            break
        except Exception as e:
            print(f"\n  ❌ Error: {e}")
            if DEBUG:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    if "--gui" in sys.argv:
        from gui import run_gui
        run_gui()
    else:
        main()
