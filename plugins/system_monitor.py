"""
JARVIS Plugin: System Monitor
==============================
Full system monitoring and process management via natural language.
Covers: CPU, RAM, disk, processes, services, pm2, logs, uptime,
        temperature, GPU, users, startup apps, and system control.

No extra Python dependencies — uses psutil if available,
falls back to /proc and system commands if not.
"""

import os
import subprocess
import shutil
import time
from datetime import datetime, timedelta
from core.plugin_base import JarvisPlugin


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list | str, timeout: int = 30, shell: bool = False) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, shell=shell
        )
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        cmd_name = cmd if isinstance(cmd, str) else cmd[0]
        return 1, "", f"Command not found: {cmd_name}"
    except Exception as e:
        return 1, "", str(e)


def _sep(n: int = 50) -> str:
    return "─" * n


def _fmt_bytes(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _bar(pct: float, width: int = 20) -> str:
    filled = int(pct / 100 * width)
    bar    = "█" * filled + "░" * (width - filled)
    color  = "🟢" if pct < 60 else ("🟡" if pct < 85 else "🔴")
    return f"{color} [{bar}] {pct:.1f}%"


def _psutil_available() -> bool:
    try:
        import psutil  # noqa
        return True
    except ImportError:
        return False


# ── Plugin ─────────────────────────────────────────────────────────────────────

class SystemMonitorPlugin(JarvisPlugin):
    NAME        = "system"
    CATEGORY    = "system"
    DESCRIPTION = "System monitor — CPU, RAM, disk, processes, pm2, services, logs"

    ACTIONS = [
        # overview
        "system_overview", "overview", "system_info", "sysinfo",
        # cpu
        "cpu_usage", "cpu", "cpu_info",
        # memory
        "ram_usage", "ram", "memory", "memory_usage",
        # disk
        "disk_usage", "disk", "disk_info", "storage",
        # processes
        "list_processes", "processes", "ps", "top_processes",
        "find_process", "search_process",
        "kill_process", "kill",
        "process_info", "process_details",
        # uptime
        "uptime", "system_uptime",
        # temperature
        "temperature", "temp", "cpu_temp",
        # gpu
        "gpu_usage", "gpu", "gpu_info",
        # users
        "logged_users", "who", "users",
        # services (systemd)
        "list_services", "services",
        "service_status", "check_service",
        "start_service",
        "stop_service",
        "restart_service",
        "enable_service",
        "disable_service",
        # pm2
        "pm2_list", "pm2_status",
        "pm2_start",
        "pm2_stop",
        "pm2_restart",
        "pm2_delete",
        "pm2_logs",
        "pm2_save",
        "pm2_resurrect",
        "pm2_monit",
        # logs
        "system_logs", "logs", "journalctl",
        "app_logs", "tail_log",
        # network usage
        "network_usage", "bandwidth",
        # system control
        "reboot", "shutdown", "sleep",
        # open files / ports by process
        "open_files", "lsof",
        "process_ports", "ports_by_process",
    ]

    ACTIONS_PROMPT = """
SYSTEM MONITOR (category: "system"):
  system_overview   params: {}                              ← full system snapshot
  cpu_usage         params: {}                              ← CPU % per core
  ram_usage         params: {}                              ← RAM usage breakdown
  disk_usage        params: {"path":"/"}                   ← disk space
  list_processes    params: {"count":15,"sort":"cpu"}       ← top processes
  find_process      params: {"name":"nginx"}                ← find process by name
  kill_process      params: {"name":"firefox","pid":1234}  ← kill process
  process_info      params: {"pid":1234}                   ← details of one process
  uptime            params: {}                              ← system uptime + load
  temperature       params: {}                              ← CPU temperature
  gpu_usage         params: {}                              ← GPU stats (nvidia/amd)
  logged_users      params: {}                              ← who is logged in
  list_services     params: {"filter":"running"}           ← systemd services
  service_status    params: {"name":"nginx"}               ← service status
  start_service     params: {"name":"nginx"}               ← start service
  stop_service      params: {"name":"nginx"}               ← stop service
  restart_service   params: {"name":"nginx"}               ← restart service
  pm2_list          params: {}                              ← list pm2 processes
  pm2_start         params: {"name":"app","script":"app.js"}
  pm2_stop          params: {"name":"app"}
  pm2_restart       params: {"name":"app"}
  pm2_delete        params: {"name":"app"}
  pm2_logs          params: {"name":"app","lines":50}      ← last N lines of pm2 logs
  pm2_save          params: {}                              ← save pm2 process list
  system_logs       params: {"lines":30,"service":""}      ← journalctl logs
  tail_log          params: {"path":"/var/log/app.log","lines":30}
  network_usage     params: {}                              ← bytes in/out per interface
  open_files        params: {"pid":1234}                   ← open files by process
  reboot            params: {}                              ← reboot system
  shutdown          params: {"delay":0}                    ← shutdown system

  Examples:
  "how much RAM am I using"    → {"category":"system","action":"ram_usage","params":{},"message":"Checking RAM."}
  "show top processes by cpu"  → {"category":"system","action":"list_processes","params":{"sort":"cpu"},"message":"Listing processes."}
  "kill process firefox"       → {"category":"system","action":"kill_process","params":{"name":"firefox"},"message":"Killing firefox."}
  "pm2 list"                   → {"category":"system","action":"pm2_list","params":{},"message":"Listing pm2 processes."}
  "show last 50 lines of pm2 logs for api" → {"category":"system","action":"pm2_logs","params":{"name":"api","lines":50},"message":"Showing pm2 logs."}
  "restart nginx service"      → {"category":"system","action":"restart_service","params":{"name":"nginx"},"message":"Restarting nginx."}
  "full system overview"       → {"category":"system","action":"system_overview","params":{},"message":"System overview."}"""

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def handle(self, action: str, params: dict) -> str:
        dispatch = {
            "system_overview":  self._overview,
            "overview":         self._overview,
            "system_info":      self._overview,
            "sysinfo":          self._overview,
            "cpu_usage":        self._cpu,
            "cpu":              self._cpu,
            "cpu_info":         self._cpu,
            "ram_usage":        self._ram,
            "ram":              self._ram,
            "memory":           self._ram,
            "memory_usage":     self._ram,
            "disk_usage":       self._disk,
            "disk":             self._disk,
            "disk_info":        self._disk,
            "storage":          self._disk,
            "list_processes":   self._processes,
            "processes":        self._processes,
            "ps":               self._processes,
            "top_processes":    self._processes,
            "find_process":     self._find_process,
            "search_process":   self._find_process,
            "kill_process":     self._kill,
            "kill":             self._kill,
            "process_info":     self._process_info,
            "process_details":  self._process_info,
            "uptime":           self._uptime,
            "system_uptime":    self._uptime,
            "temperature":      self._temperature,
            "temp":             self._temperature,
            "cpu_temp":         self._temperature,
            "gpu_usage":        self._gpu,
            "gpu":              self._gpu,
            "gpu_info":         self._gpu,
            "logged_users":     self._users,
            "who":              self._users,
            "users":            self._users,
            "list_services":    self._list_services,
            "services":         self._list_services,
            "service_status":   self._service_status,
            "check_service":    self._service_status,
            "start_service":    self._service_start,
            "stop_service":     self._service_stop,
            "restart_service":  self._service_restart,
            "enable_service":   self._service_enable,
            "disable_service":  self._service_disable,
            "pm2_list":         self._pm2_list,
            "pm2_status":       self._pm2_list,
            "pm2_start":        self._pm2_start,
            "pm2_stop":         self._pm2_stop,
            "pm2_restart":      self._pm2_restart,
            "pm2_delete":       self._pm2_delete,
            "pm2_logs":         self._pm2_logs,
            "pm2_save":         self._pm2_save,
            "pm2_resurrect":    self._pm2_resurrect,
            "pm2_monit":        self._pm2_monit,
            "system_logs":      self._system_logs,
            "logs":             self._system_logs,
            "journalctl":       self._system_logs,
            "app_logs":         self._tail_log,
            "tail_log":         self._tail_log,
            "network_usage":    self._network_usage,
            "bandwidth":        self._network_usage,
            "open_files":       self._open_files,
            "lsof":             self._open_files,
            "process_ports":    self._process_ports,
            "ports_by_process": self._process_ports,
            "reboot":           self._reboot,
            "shutdown":         self._shutdown,
            "sleep":            self._sleep,
        }
        fn = dispatch.get(action)
        if fn:
            return fn(params)
        return f"  Unknown system action: '{action}'"

    # ── Overview ──────────────────────────────────────────────────────────────

    def _overview(self, params: dict) -> str:
        result = f"  💻 System Overview  [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n"
        result += f"  {_sep()}\n"

        # Uptime
        _, up, _ = _run(["uptime", "-p"])
        _, load, _ = _run(["cat", "/proc/loadavg"])
        load_vals = load.split()[:3] if load else ["?", "?", "?"]
        result += f"  ⏱️  Uptime:  {up or 'unknown'}\n"
        result += f"  📊 Load:    {' '.join(load_vals)} (1/5/15 min)\n"
        result += f"  {_sep()}\n"

        # CPU
        cpu_pct = self._get_cpu_pct()
        result += f"  🖥️  CPU:     {_bar(cpu_pct)}\n"

        # RAM
        ram = self._get_ram()
        if ram:
            result += f"  🧠 RAM:     {_bar(ram['pct'])}  ({_fmt_bytes(ram['used'])} / {_fmt_bytes(ram['total'])})\n"

        # Disk
        _, df_out, _ = _run(["df", "-h", "--output=target,pcent,used,size", "/"])
        if df_out:
            lines = df_out.splitlines()
            if len(lines) > 1:
                parts = lines[1].split()
                pct_str = parts[1].replace("%", "") if len(parts) > 1 else "0"
                try:
                    pct = float(pct_str)
                except Exception:
                    pct = 0
                used = parts[2] if len(parts) > 2 else "?"
                size = parts[3] if len(parts) > 3 else "?"
                result += f"  💾 Disk:    {_bar(pct)}  ({used} / {size})\n"

        result += f"  {_sep()}\n"

        # Top 5 processes by CPU
        result += "  🔥 Top Processes (CPU):\n"
        _, ps_out, _ = _run([
            "ps", "aux", "--sort=-%cpu",
            "--no-headers", "-o", "pid,pcpu,pmem,comm"
        ])
        if ps_out:
            for line in ps_out.splitlines()[:5]:
                parts = line.split()
                if len(parts) >= 4:
                    pid, cpu, mem, name = parts[0], parts[1], parts[2], parts[3]
                    result += f"    PID {pid:<7} CPU {cpu:>5}%  MEM {mem:>5}%  {name}\n"

        # Services check
        result += f"  {_sep()}\n"
        _, svc_out, _ = _run([
            "systemctl", "list-units", "--type=service",
            "--state=failed", "--no-legend", "--no-pager"
        ])
        failed = len(svc_out.splitlines()) if svc_out.strip() else 0
        result += f"  ⚠️  Failed services: {failed}\n"

        # PM2
        if shutil.which("pm2"):
            _, pm2_out, _ = _run(["pm2", "jlist"], timeout=10)
            try:
                import json
                procs = json.loads(pm2_out) if pm2_out else []
                online  = sum(1 for p in procs if p.get("pm2_env", {}).get("status") == "online")
                stopped = len(procs) - online
                result += f"  🟢 PM2: {online} online, {stopped} stopped\n"
            except Exception:
                result += f"  🔄 PM2: installed\n"

        return result.rstrip()

    # ── CPU ───────────────────────────────────────────────────────────────────

    def _get_cpu_pct(self) -> float:
        """Get CPU usage percentage."""
        if _psutil_available():
            import psutil
            return psutil.cpu_percent(interval=1)
        # Fallback: read /proc/stat twice
        try:
            def read_stat():
                with open("/proc/stat") as f:
                    line = f.readline()
                vals = list(map(int, line.split()[1:]))
                idle = vals[3]
                total = sum(vals)
                return idle, total
            i1, t1 = read_stat()
            time.sleep(0.5)
            i2, t2 = read_stat()
            idle_delta  = i2 - i1
            total_delta = t2 - t1
            return round((1 - idle_delta / total_delta) * 100, 1) if total_delta else 0.0
        except Exception:
            return 0.0

    def _cpu(self, params: dict) -> str:
        pct = self._get_cpu_pct()
        result = f"  🖥️  CPU Usage:\n  {_sep()}\n"
        result += f"  Overall: {_bar(pct)}\n"

        # Per-core if psutil available
        if _psutil_available():
            import psutil
            cores = psutil.cpu_percent(interval=0.5, percpu=True)
            result += f"  {_sep()}\n  Per Core:\n"
            for i, c in enumerate(cores):
                result += f"    Core {i}: {_bar(c)}\n"
            freq = psutil.cpu_freq()
            if freq:
                result += f"  {_sep()}\n"
                result += f"  Frequency: {freq.current:.0f} MHz (max: {freq.max:.0f} MHz)\n"
            count = psutil.cpu_count(logical=False)
            logical = psutil.cpu_count(logical=True)
            result += f"  Cores: {count} physical, {logical} logical\n"
        else:
            # fallback: /proc/cpuinfo
            _, cpuinfo, _ = _run(["grep", "-m1", "model name", "/proc/cpuinfo"])
            if cpuinfo:
                model = cpuinfo.split(":")[1].strip() if ":" in cpuinfo else cpuinfo
                result += f"  Model: {model}\n"
            _, cores_out, _ = _run(["nproc"])
            result += f"  Cores: {cores_out or '?'}\n"

        # Load average
        _, load, _ = _run(["cat", "/proc/loadavg"])
        if load:
            vals = load.split()[:3]
            result += f"  Load avg: {vals[0]} / {vals[1]} / {vals[2]} (1/5/15 min)\n"

        return result.rstrip()

    # ── RAM ───────────────────────────────────────────────────────────────────

    def _get_ram(self) -> dict | None:
        if _psutil_available():
            import psutil
            m = psutil.virtual_memory()
            return {
                "total":     m.total,
                "used":      m.used,
                "available": m.available,
                "pct":       m.percent,
                "cached":    getattr(m, "cached", 0),
                "buffers":   getattr(m, "buffers", 0),
            }
        try:
            info = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1]) * 1024
            total     = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            used      = total - available
            pct       = (used / total * 100) if total else 0
            return {
                "total":     total,
                "used":      used,
                "available": available,
                "pct":       round(pct, 1),
                "cached":    info.get("Cached", 0),
                "buffers":   info.get("Buffers", 0),
            }
        except Exception:
            return None

    def _ram(self, params: dict) -> str:
        ram = self._get_ram()
        if not ram:
            return "  ⚠️  Could not read memory info."

        result = f"  🧠 Memory Usage:\n  {_sep()}\n"
        result += f"  RAM:      {_bar(ram['pct'])}\n"
        result += f"  {_sep()}\n"
        result += f"  Total:     {_fmt_bytes(ram['total'])}\n"
        result += f"  Used:      {_fmt_bytes(ram['used'])}\n"
        result += f"  Available: {_fmt_bytes(ram['available'])}\n"
        if ram.get("cached"):
            result += f"  Cached:    {_fmt_bytes(ram['cached'])}\n"
        if ram.get("buffers"):
            result += f"  Buffers:   {_fmt_bytes(ram['buffers'])}\n"

        # Swap
        if _psutil_available():
            import psutil
            swap = psutil.swap_memory()
            if swap.total > 0:
                result += f"  {_sep()}\n"
                result += f"  Swap:     {_bar(swap.percent)}  ({_fmt_bytes(swap.used)} / {_fmt_bytes(swap.total)})\n"
        else:
            _, free_out, _ = _run(["free", "-h"])
            if free_out:
                for line in free_out.splitlines():
                    if line.lower().startswith("swap"):
                        result += f"  {_sep()}\n  {line}\n"

        return result.rstrip()

    # ── Disk ──────────────────────────────────────────────────────────────────

    def _disk(self, params: dict) -> str:
        path = params.get("path", params.get("mount", "/"))
        _, out, err = _run(["df", "-h", "--output=target,fstype,size,used,avail,pcent", path])
        if err and not out:
            return f"  ⚠️  {err}"

        result = f"  💾 Disk Usage:\n  {_sep()}\n"
        lines  = out.splitlines()
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    mount, fstype, size, used, avail, pct_str = parts
                    try:
                        pct = float(pct_str.replace("%", ""))
                    except Exception:
                        pct = 0
                    result += f"  {mount}\n"
                    result += f"    {_bar(pct)}\n"
                    result += f"    Size: {size}  Used: {used}  Free: {avail}  Type: {fstype}\n\n"

        # All mounts
        _, all_out, _ = _run(["df", "-h", "--output=target,size,used,avail,pcent"])
        if all_out:
            result += f"  {_sep()}\n  All Mounts:\n"
            for line in all_out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 5 and not parts[0].startswith("/dev/loop"):
                    result += f"    {parts[0]:<25} {parts[4]:>5}  free: {parts[3]}\n"

        return result.rstrip()

    # ── Processes ─────────────────────────────────────────────────────────────

    def _processes(self, params: dict) -> str:
        count  = int(params.get("count", params.get("n", params.get("limit", 15))))
        sort   = params.get("sort", params.get("by", "cpu")).lower()
        sort_flag = f"-%{sort}" if sort in ("cpu", "mem") else "-%cpu"

        _, out, err = _run([
            "ps", "aux", f"--sort={sort_flag}",
            "--no-headers", "-o",
            "pid,user,%cpu,%mem,vsz,rss,stat,comm,args"
        ])
        if err and not out:
            return f"  ⚠️  {err}"

        lines = out.splitlines()[:count]
        result = f"  🔥 Top {len(lines)} Processes (by {sort.upper()}):\n  {_sep()}\n"
        result += f"  {'PID':<8} {'USER':<12} {'CPU%':>5} {'MEM%':>5} {'RSS':>8}  COMMAND\n"
        result += f"  {_sep()}\n"

        for line in lines:
            parts = line.split(None, 8)
            if len(parts) >= 8:
                pid   = parts[0]
                user  = parts[1][:10]
                cpu   = parts[2]
                mem   = parts[3]
                rss   = _fmt_bytes(int(parts[5]) * 1024) if parts[5].isdigit() else parts[5]
                cmd   = parts[7][:40]
                result += f"  {pid:<8} {user:<12} {cpu:>5} {mem:>5} {rss:>8}  {cmd}\n"

        return result.rstrip()

    def _find_process(self, params: dict) -> str:
        name = params.get("name", params.get("process", params.get("query", ""))).strip()
        if not name:
            return "  ⚠️  No process name specified."

        _, out, _ = _run(["pgrep", "-a", "-i", name])
        if not out:
            _, out, _ = _run(["ps", "aux"])
            matches = [l for l in out.splitlines() if name.lower() in l.lower()]
            if not matches:
                return f"  ℹ️  No process matching '{name}' found."
            out = "\n".join(matches)

        result = f"  🔍 Processes matching '{name}':\n  {_sep()}\n"
        for line in out.splitlines()[:20]:
            result += f"  {line}\n"
        return result.rstrip()

    def _kill(self, params: dict) -> str:
        name   = params.get("name", params.get("process", "")).strip()
        pid    = params.get("pid", params.get("id", ""))
        signal = params.get("signal", params.get("sig", "15"))  # 15=SIGTERM, 9=SIGKILL

        if pid:
            code, out, err = _run(["kill", f"-{signal}", str(pid)])
            if code == 0:
                return f"  ✅ Killed process PID {pid} (signal {signal})"
            return f"  ⚠️  Could not kill PID {pid}: {err}"

        if not name:
            return "  ⚠️  Specify name or pid."

        code, out, err = _run(["pkill", f"-{signal}", "-i", name])
        if code == 0:
            return f"  ✅ Killed process: '{name}' (signal {signal})"
        return f"  ⚠️  No process found: '{name}'"

    def _process_info(self, params: dict) -> str:
        pid = str(params.get("pid", params.get("id", ""))).strip()
        if not pid:
            return "  ⚠️  No PID specified."

        if _psutil_available():
            import psutil
            try:
                p = psutil.Process(int(pid))
                with p.oneshot():
                    result = (
                        f"  📋 Process Info — PID {pid}\n  {_sep()}\n"
                        f"  Name:      {p.name()}\n"
                        f"  Status:    {p.status()}\n"
                        f"  User:      {p.username()}\n"
                        f"  CPU:       {p.cpu_percent(interval=0.5):.1f}%\n"
                        f"  Memory:    {_fmt_bytes(p.memory_info().rss)}\n"
                        f"  Created:   {datetime.fromtimestamp(p.create_time()).strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"  CWD:       {p.cwd()}\n"
                        f"  Cmdline:   {' '.join(p.cmdline())[:80]}\n"
                    )
                    try:
                        conns = p.connections()
                        if conns:
                            result += f"  Ports:     {', '.join(str(c.laddr.port) for c in conns if c.laddr)}\n"
                    except Exception:
                        pass
                return result.rstrip()
            except psutil.NoSuchProcess:
                return f"  ⚠️  No process with PID {pid}"
            except Exception as e:
                return f"  ⚠️  {e}"

        # Fallback
        _, out, _ = _run(["ps", "-p", pid, "-o", "pid,user,%cpu,%mem,stat,comm,args"])
        if not out:
            return f"  ⚠️  No process with PID {pid}"
        return f"  📋 Process {pid}:\n  {_sep()}\n{out}"

    # ── Uptime ────────────────────────────────────────────────────────────────

    def _uptime(self, params: dict) -> str:
        _, up_p, _  = _run(["uptime", "-p"])
        _, up_s, _  = _run(["uptime"])
        _, load, _  = _run(["cat", "/proc/loadavg"])
        _, boot, _  = _run(["who", "-b"])

        load_vals = load.split()[:3] if load else ["?", "?", "?"]
        result = (
            f"  ⏱️  System Uptime\n  {_sep()}\n"
            f"  Up:       {up_p or 'unknown'}\n"
            f"  Load avg: {load_vals[0]} / {load_vals[1]} / {load_vals[2]} (1/5/15 min)\n"
        )
        if boot:
            result += f"  Boot:     {boot.split('system boot')[1].strip() if 'system boot' in boot else boot}\n"

        # CPU count for context
        _, nproc, _ = _run(["nproc"])
        if nproc:
            result += f"  CPU cores: {nproc} (load > {nproc} = overloaded)\n"

        return result.rstrip()

    # ── Temperature ───────────────────────────────────────────────────────────

    def _temperature(self, params: dict) -> str:
        if _psutil_available():
            import psutil
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    result = f"  🌡️  CPU Temperature:\n  {_sep()}\n"
                    for name, readings in temps.items():
                        for r in readings:
                            label = r.label or name
                            icon  = "🔴" if r.current > 80 else ("🟡" if r.current > 65 else "🟢")
                            result += f"  {icon} {label}: {r.current:.1f}°C"
                            if r.high:
                                result += f"  (high: {r.high:.0f}°C)"
                            result += "\n"
                    return result.rstrip()
            except Exception:
                pass

        # Fallback: read thermal zones
        result = f"  🌡️  Temperature:\n  {_sep()}\n"
        found  = False
        for i in range(10):
            zone = f"/sys/class/thermal/thermal_zone{i}/temp"
            if os.path.exists(zone):
                try:
                    with open(zone) as f:
                        temp = int(f.read().strip()) / 1000
                    icon = "🔴" if temp > 80 else ("🟡" if temp > 65 else "🟢")
                    result += f"  {icon} Zone {i}: {temp:.1f}°C\n"
                    found = True
                except Exception:
                    pass

        if not found:
            result += "  ℹ️  Temperature sensors not available.\n"
            result += "  Install lm-sensors: sudo apt install lm-sensors && sudo sensors-detect\n"

        return result.rstrip()

    # ── GPU ───────────────────────────────────────────────────────────────────

    def _gpu(self, params: dict) -> str:
        # Try nvidia-smi
        if shutil.which("nvidia-smi"):
            _, out, _ = _run([
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,utilization.memory,"
                "memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits"
            ])
            if out:
                parts = [p.strip() for p in out.split(",")]
                if len(parts) >= 6:
                    return (
                        f"  🎮 GPU (NVIDIA):\n  {_sep()}\n"
                        f"  Name:       {parts[0]}\n"
                        f"  GPU Usage:  {_bar(float(parts[1]))}\n"
                        f"  VRAM Usage: {_bar(float(parts[2]))}\n"
                        f"  VRAM:       {parts[3]} MB / {parts[4]} MB\n"
                        f"  Temp:       {parts[5]}°C\n"
                    )

        # Try rocm-smi (AMD)
        if shutil.which("rocm-smi"):
            _, out, _ = _run(["rocm-smi", "--showuse", "--showmemuse", "--showtemp"])
            if out:
                return f"  🎮 GPU (AMD):\n  {_sep()}\n{out}"

        # Try glxinfo
        if shutil.which("glxinfo"):
            _, out, _ = _run(["glxinfo", "-B"])
            if out:
                lines = [l for l in out.splitlines() if "renderer" in l.lower() or "vendor" in l.lower()]
                result = f"  🎮 GPU Info:\n  {_sep()}\n"
                for l in lines[:5]:
                    result += f"  {l}\n"
                return result.rstrip()

        return (
            "  ℹ️  No GPU monitoring tool found.\n"
            "  For NVIDIA: nvidia-smi (install nvidia-utils)\n"
            "  For AMD:    rocm-smi (install rocm)"
        )

    # ── Users ─────────────────────────────────────────────────────────────────

    def _users(self, params: dict) -> str:
        _, out, _ = _run(["who", "-a"])
        if not out:
            _, out, _ = _run(["who"])
        if not out:
            return "  ℹ️  No users logged in (or 'who' not available)."
        return f"  👥 Logged-in Users:\n  {_sep()}\n{out}"

    # ── Services (systemd) ────────────────────────────────────────────────────

    def _list_services(self, params: dict) -> str:
        filter_ = params.get("filter", params.get("state", "")).lower()
        args    = ["systemctl", "list-units", "--type=service", "--no-pager", "--no-legend"]

        if filter_ == "running":
            args += ["--state=running"]
        elif filter_ == "failed":
            args += ["--state=failed"]
        elif filter_ == "inactive":
            args += ["--state=inactive"]

        _, out, err = _run(args)
        if err and not out:
            return f"  ⚠️  {err}\n  Is systemd running?"

        lines  = out.splitlines()[:30]
        result = f"  ⚙️  Services ({filter_ or 'all'}):\n  {_sep()}\n"
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                name   = parts[0][:35]
                state  = parts[2]
                icon   = "🟢" if state == "running" else ("🔴" if state == "failed" else "⚪")
                result += f"  {icon} {name:<37} {state}\n"

        if len(out.splitlines()) > 30:
            result += f"  ... and {len(out.splitlines())-30} more\n"

        return result.rstrip()

    def _service_action(self, name: str, action: str) -> str:
        if not name:
            return f"  ⚠️  No service name specified."
        code, out, err = _run(["systemctl", action, name])
        icons = {"start":"▶️ ", "stop":"⏹️ ", "restart":"🔄",
                 "enable":"✅", "disable":"🚫", "status":"📋"}
        icon  = icons.get(action, "⚙️ ")
        if code == 0 or action == "status":
            return f"  {icon} {action.title()} '{name}':\n  {_sep()}\n{out or '  Done.'}"
        return f"  ⚠️  Could not {action} '{name}':\n  {err}"

    def _service_status(self, params: dict) -> str:
        name = params.get("name", params.get("service", "")).strip()
        return self._service_action(name, "status")

    def _service_start(self, params: dict) -> str:
        name = params.get("name", params.get("service", "")).strip()
        return self._service_action(name, "start")

    def _service_stop(self, params: dict) -> str:
        name = params.get("name", params.get("service", "")).strip()
        return self._service_action(name, "stop")

    def _service_restart(self, params: dict) -> str:
        name = params.get("name", params.get("service", "")).strip()
        return self._service_action(name, "restart")

    def _service_enable(self, params: dict) -> str:
        name = params.get("name", params.get("service", "")).strip()
        return self._service_action(name, "enable")

    def _service_disable(self, params: dict) -> str:
        name = params.get("name", params.get("service", "")).strip()
        return self._service_action(name, "disable")

    # ── PM2 ───────────────────────────────────────────────────────────────────

    def _pm2_check(self) -> str | None:
        if not shutil.which("pm2"):
            return (
                "  ⚠️  pm2 is not installed.\n"
                "  Install: npm install -g pm2"
            )
        return None

    def _pm2_list(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err

        _, out, _ = _run(["pm2", "jlist"], timeout=15)
        try:
            import json
            procs = json.loads(out) if out else []
        except Exception:
            # Fallback to text output
            _, out, _ = _run(["pm2", "list", "--no-color"], timeout=15)
            return f"  🔄 PM2 Processes:\n  {_sep()}\n{out or '  No processes.'}"

        if not procs:
            return "  ℹ️  No PM2 processes running."

        result = f"  🔄 PM2 Processes ({len(procs)}):\n  {_sep()}\n"
        result += f"  {'ID':<4} {'NAME':<20} {'STATUS':<10} {'CPU%':>5} {'MEM':>8}  {'RESTARTS'}\n"
        result += f"  {_sep()}\n"

        for p in procs:
            env    = p.get("pm2_env", {})
            name   = p.get("name", "?")[:18]
            pid    = p.get("pid", "?")
            status = env.get("status", "?")
            cpu    = p.get("monit", {}).get("cpu", 0)
            mem    = p.get("monit", {}).get("memory", 0)
            rstrt  = env.get("restart_time", 0)
            pm_id  = env.get("pm_id", "?")
            icon   = "🟢" if status == "online" else ("🔴" if status == "errored" else "⚪")
            result += (f"  {icon} {str(pm_id):<3} {name:<20} {status:<10} "
                       f"{cpu:>4}% {_fmt_bytes(mem):>8}  ×{rstrt}\n")

        return result.rstrip()

    def _pm2_start(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err
        name   = params.get("name", params.get("app", "")).strip()
        script = params.get("script", params.get("file", "")).strip()
        if not name and not script:
            return "  ⚠️  Specify name or script."
        args = ["pm2", "start"]
        if script:
            args.append(script)
            if name: args += ["--name", name]
        else:
            args.append(name)
        code, out, err_msg = _run(args, timeout=30)
        return (f"  ✅ PM2 started: {name or script}\n{out}"
                if code == 0 else f"  ⚠️  {err_msg}")

    def _pm2_stop(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err
        name = params.get("name", params.get("app", params.get("id", "all"))).strip()
        code, out, err_msg = _run(["pm2", "stop", name], timeout=15)
        return (f"  ⏹️  PM2 stopped: {name}" if code == 0 else f"  ⚠️  {err_msg}")

    def _pm2_restart(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err
        name = params.get("name", params.get("app", params.get("id", "all"))).strip()
        code, out, err_msg = _run(["pm2", "restart", name], timeout=15)
        return (f"  🔄 PM2 restarted: {name}" if code == 0 else f"  ⚠️  {err_msg}")

    def _pm2_delete(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err
        name = params.get("name", params.get("app", params.get("id", ""))).strip()
        if not name:
            return "  ⚠️  No process name specified."
        code, out, err_msg = _run(["pm2", "delete", name], timeout=15)
        return (f"  🗑️  PM2 deleted: {name}" if code == 0 else f"  ⚠️  {err_msg}")

    def _pm2_logs(self, params: dict) -> str:
        """Get last N lines of pm2 logs — never streams, always returns immediately."""
        err = self._pm2_check()
        if err: return err

        name  = params.get("name", params.get("app", params.get("id", ""))).strip()
        lines = int(params.get("lines", params.get("n", params.get("count", 50))))

        # pm2 logs --lines N --nostream  ← key flag that prevents hanging
        args = ["pm2", "logs", "--lines", str(lines), "--nostream", "--no-color"]
        if name:
            args.insert(2, name)

        code, out, err_msg = _run(args, timeout=15)
        output = out or err_msg or "No logs available."

        label = f"'{name}'" if name else "all processes"
        return (f"  📋 PM2 Logs — {label} (last {lines} lines):\n"
                f"  {_sep()}\n"
                f"{output}\n"
                f"  {_sep()}")

    def _pm2_save(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err
        code, out, err_msg = _run(["pm2", "save"], timeout=15)
        return (f"  💾 PM2 process list saved." if code == 0 else f"  ⚠️  {err_msg}")

    def _pm2_resurrect(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err
        code, out, err_msg = _run(["pm2", "resurrect"], timeout=15)
        return (f"  ✅ PM2 processes restored." if code == 0 else f"  ⚠️  {err_msg}")

    def _pm2_monit(self, params: dict) -> str:
        err = self._pm2_check()
        if err: return err
        return (
            "  ℹ️  pm2 monit is an interactive dashboard — it can't run inside JARVIS.\n"
            "  Open a terminal and run:  pm2 monit"
        )

    # ── Logs ──────────────────────────────────────────────────────────────────

    def _system_logs(self, params: dict) -> str:
        lines   = int(params.get("lines", params.get("n", 30)))
        service = params.get("service", params.get("unit", "")).strip()
        level   = params.get("level", params.get("priority", "")).strip()

        args = ["journalctl", f"-n{lines}", "--no-pager", "--no-hostname"]
        if service: args += ["-u", service]
        if level:   args += [f"-p{level}"]

        code, out, err = _run(args, timeout=15)
        if code != 0 and not out:
            return f"  ⚠️  {err or 'journalctl not available'}"

        label = f"— {service}" if service else ""
        return (f"  📋 System Logs {label} (last {lines} lines):\n"
                f"  {_sep()}\n{out}")

    def _tail_log(self, params: dict) -> str:
        path  = os.path.expanduser(
            params.get("path", params.get("file", params.get("log", ""))))
        lines = int(params.get("lines", params.get("n", 30)))

        if not path:
            return "  ⚠️  No log file path specified."
        if not os.path.exists(path):
            return f"  ⚠️  File not found: {path}"

        code, out, err = _run(["tail", f"-n{lines}", path])
        if code != 0:
            return f"  ⚠️  {err}"

        return (f"  📋 {path} (last {lines} lines):\n"
                f"  {_sep()}\n{out}")

    # ── Network Usage ─────────────────────────────────────────────────────────

    def _network_usage(self, params: dict) -> str:
        if _psutil_available():
            import psutil
            counters = psutil.net_io_counters(pernic=True)
            result   = f"  🌐 Network Usage:\n  {_sep()}\n"
            for iface, stats in counters.items():
                if iface == "lo": continue
                result += (f"  {iface}:\n"
                           f"    ↑ Sent:     {_fmt_bytes(stats.bytes_sent)}\n"
                           f"    ↓ Received: {_fmt_bytes(stats.bytes_recv)}\n"
                           f"    Packets:    {stats.packets_sent} sent / {stats.packets_recv} recv\n\n")
            return result.rstrip()

        # Fallback: /proc/net/dev
        try:
            result = f"  🌐 Network Usage:\n  {_sep()}\n"
            with open("/proc/net/dev") as f:
                lines = f.readlines()[2:]
            for line in lines:
                parts = line.split()
                if len(parts) >= 10:
                    iface = parts[0].rstrip(":")
                    if iface == "lo": continue
                    rx = int(parts[1])
                    tx = int(parts[9])
                    result += (f"  {iface}:\n"
                               f"    ↓ Received: {_fmt_bytes(rx)}\n"
                               f"    ↑ Sent:     {_fmt_bytes(tx)}\n\n")
            return result.rstrip()
        except Exception as e:
            return f"  ⚠️  Could not read network stats: {e}"

    # ── Open Files / Ports ────────────────────────────────────────────────────

    def _open_files(self, params: dict) -> str:
        pid  = str(params.get("pid", params.get("id", ""))).strip()
        name = params.get("name", params.get("process", "")).strip()

        if not shutil.which("lsof"):
            return "  ⚠️  lsof not installed.\n  Install: sudo apt install lsof"

        args = ["lsof"]
        if pid:   args += ["-p", pid]
        elif name: args += ["-c", name]
        else:
            return "  ⚠️  Specify pid or name."

        code, out, err = _run(args, timeout=15)
        if not out:
            return f"  ⚠️  {err or 'No open files found.'}"

        lines  = out.splitlines()[:30]
        result = f"  📂 Open Files (PID {pid or name}):\n  {_sep()}\n"
        for line in lines:
            result += f"  {line}\n"
        return result.rstrip()

    def _process_ports(self, params: dict) -> str:
        name = params.get("name", params.get("process", "")).strip()
        pid  = str(params.get("pid", "")).strip()

        if _psutil_available():
            import psutil
            result = f"  🔌 Ports by Process:\n  {_sep()}\n"
            for proc in psutil.process_iter(["pid", "name", "connections"]):
                try:
                    pname = proc.info["name"]
                    if name and name.lower() not in pname.lower(): continue
                    if pid and str(proc.info["pid"]) != pid: continue
                    conns = proc.info["connections"]
                    if conns:
                        for c in conns:
                            if c.laddr:
                                result += f"  {pname:<25} PID {proc.info['pid']:<7} :{c.laddr.port}\n"
                except Exception:
                    continue
            return result.rstrip()

        # Fallback: ss or netstat
        tool = "ss" if shutil.which("ss") else ("netstat" if shutil.which("netstat") else None)
        if not tool:
            return "  ⚠️  ss/netstat not found. Install: sudo apt install iproute2"

        args = [tool, "-tulpn"]
        code, out, err = _run(args)
        if name and out:
            out = "\n".join(l for l in out.splitlines() if name.lower() in l.lower() or "State" in l)

        return f"  🔌 Network Connections:\n  {_sep()}\n{out}"

    # ── System Control ────────────────────────────────────────────────────────

    def _reboot(self, params: dict) -> str:
        return (
            "  ⚠️  Reboot requires confirmation.\n"
            "  Run manually:  sudo reboot\n"
            "  Or schedule:   sudo shutdown -r +1 (in 1 minute)"
        )

    def _shutdown(self, params: dict) -> str:
        return (
            "  ⚠️  Shutdown requires confirmation.\n"
            "  Run manually:  sudo shutdown now\n"
            "  Or schedule:   sudo shutdown +5 (in 5 minutes)"
        )

    def _sleep(self, params: dict) -> str:
        return (
            "  ⚠️  Sleep requires confirmation.\n"
            "  Run manually:  systemctl suspend"
        )
