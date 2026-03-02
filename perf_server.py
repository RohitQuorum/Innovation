"""
Server Performance Tracker - Backend Server (Multi-Server Support)
Reads CSV performance data and serves JSON API + HTML dashboard.
Threshold filtering is done dynamically from all_*.csv data.
"""
import http.server
import json
import csv
import os
import time
import glob
import re
import subprocess
import signal
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
from threading import Lock

CSV_DIR = r"C:\Users\rohit.gaikwad\OneDrive - Quorum Business Solutions\perf"
PORT = 8890
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "servers_config.json")
COLLECTOR_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Collect-PerfData.ps1")
SERVER_PATTERN = re.compile(r"host_(.+?)_(\d{4}-\d{2}-\d{2})\.csv")

# Global collectors management
_collectors = {}  # {server_name: subprocess.Popen}
_collectors_lock = Lock()


# ---------------------------------------------------------------------------
# Server Configuration Management
# ---------------------------------------------------------------------------
def load_server_config():
    """Load server configuration from JSON file"""
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "servers": [
                {"name": "QDDEATAPP01.qdev.net", "enabled": True}
            ]
        }
        save_server_config(default_config)
        return default_config
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return {"servers": []}

def save_server_config(config):
    """Save server configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save config: {e}")
        return False

def get_enabled_servers():
    """Get list of enabled servers from config"""
    config = load_server_config()
    return [s["name"] for s in config.get("servers", []) if s.get("enabled", True)]

# ---------------------------------------------------------------------------
# Data cache – parses CSVs into memory, refreshes today's data every 30s
# ---------------------------------------------------------------------------
class DataCache:
    def __init__(self, csv_dir):
        self.csv_dir = csv_dir
        self._cache = {}
        self._ts = {}

    def _key(self, date_str, ftype):
        return f"{date_str}|{ftype}"

    def _stale(self, date_str, ftype):
        k = self._key(date_str, ftype)
        if k not in self._cache:
            return True
        today = datetime.now().strftime("%Y-%m-%d")
        if date_str == today and (time.time() - self._ts.get(k, 0)) > 30:
            return True
        return False

    def _find_file(self, prefix, server_slug, date_str):
        # Try published file first, fall back to _writing file
        published = os.path.join(
            self.csv_dir, f"{prefix}_{server_slug}_{date_str}.csv"
        )
        files = glob.glob(published)
        if files:
            return files[0]
        # Fallback: _writing file (live collector file)
        writing = os.path.join(
            self.csv_dir, f"{prefix}_{server_slug}_{date_str}_writing.csv"
        )
        files = glob.glob(writing)
        return files[0] if files else None

    def _get_all_server_slugs(self):
        """Find all server slugs in CSV directory"""
        slugs = set()
        for f in os.listdir(self.csv_dir):
            m = SERVER_PATTERN.match(f)
            if m:
                slugs.add(m.group(1))
            # Also check _writing files
            elif f.startswith("host_") and (f.endswith("_writing.csv") or f.endswith(".csv")):
                parts = f.replace("host_", "").replace("_writing.csv", "").replace(".csv", "")
                date_part = parts[-10:]
                slug = parts[: -(len(date_part) + 1)]
                slugs.add(slug)
        return list(slugs)

    def get_all_servers(self):
        """Get list of all servers with data"""
        slugs = self._get_all_server_slugs()
        return [{"slug": s, "name": s.replace("_", ".")} for s in slugs]

    def get_server_slug(self):
        """Get first available server slug (for backward compatibility)"""
        slugs = self._get_all_server_slugs()
        return slugs[0] if slugs else None

    def get_server_name(self):
        slug = self.get_server_slug()
        return slug.replace("_", ".") if slug else "Unknown"

    # --- available dates -----------------------------------------------
    def available_dates(self):
        dates = set()
        for f in os.listdir(self.csv_dir):
            if f.startswith("host_") or f.startswith("all_"):
                m = re.search(r"(\d{4}-\d{2}-\d{2})(?:_writing)?\.csv$", f)
                if m:
                    dates.add(m.group(1))
        return sorted(dates, reverse=True)

    # =================================================================
    # HOST DATA  (from host_*.csv)
    # =================================================================
    def host(self, date_str):
        ftype = "host"
        if self._stale(date_str, ftype):
            self._load_host(date_str)
        return self._cache.get(self._key(date_str, ftype), {})

    def _load_host(self, date_str):
        slug = self.get_server_slug()
        path = self._find_file("host", slug, date_str)
        if not path:
            return
        timestamps, cpu, used_mb, used_pct = [], [], [], []
        total_ram = 0
        with open(path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    timestamps.append(row["Timestamp"].strip())
                    cpu.append(float(row["HostCpu_Pct"]))
                    total_ram = float(row["TotalRam_MB"])
                    used_mb.append(float(row["UsedRam_MB"]))
                    used_pct.append(float(row["UsedRam_Pct"]))
                except (ValueError, KeyError):
                    continue
        if not timestamps:
            return
        data = {
            "timestamps": timestamps,
            "cpu_pct": cpu,
            "total_ram_mb": round(total_ram, 2),
            "used_ram_mb": used_mb,
            "used_ram_pct": used_pct,
            "summary": {
                "cpu_current": cpu[-1],
                "cpu_avg": round(sum(cpu) / len(cpu), 1),
                "cpu_max": max(cpu),
                "cpu_max_time": timestamps[cpu.index(max(cpu))],
                "mem_current_pct": used_pct[-1],
                "mem_avg_pct": round(sum(used_pct) / len(used_pct), 1),
                "mem_max_pct": max(used_pct),
                "mem_max_time": timestamps[used_pct.index(max(used_pct))],
                "mem_current_mb": round(used_mb[-1], 1),
            },
        }
        k = self._key(date_str, "host")
        self._cache[k] = data
        self._ts[k] = time.time()

    # =================================================================
    # ALL PROCESS DATA  (from all_*.csv – parsed once, used for everything)
    # =================================================================
    def _all_data(self, date_str):
        """Return parsed all_*.csv rows split by metric. Cached."""
        ftype = "all_parsed"
        if self._stale(date_str, ftype):
            self._load_all(date_str)
        return self._cache.get(self._key(date_str, ftype))

    def _load_all(self, date_str):
        slug = self.get_server_slug()
        path = self._find_file("all", slug, date_str)
        if not path:
            return
        cpu_rows = []
        mem_rows = []
        with open(path, "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    metric = row["Metric"].strip()
                    entry = {
                        "timestamp": row["Timestamp"].strip(),
                        "process": row["ProcessName"].strip(),
                        "pid": row["ProcessId"].strip(),
                        "value": float(row["Value"]),
                        "unit": row["Unit"].strip(),
                        "service": row.get("ServiceNames", "").strip(),
                    }
                except (ValueError, KeyError):
                    continue
                if metric == "CPU":
                    cpu_rows.append(entry)
                elif metric == "MEM":
                    mem_rows.append(entry)

        data = {"cpu": cpu_rows, "mem": mem_rows}
        k = self._key(date_str, "all_parsed")
        self._cache[k] = data
        self._ts[k] = time.time()

    # =================================================================
    # ALERTS  (computed dynamically from all_*.csv with threshold)
    # =================================================================
    def cpu_alerts(self, date_str, threshold=80):
        ad = self._all_data(date_str)
        if not ad:
            return {"alerts": [], "summary": _empty_alert_summary()}
        alerts = [r for r in ad["cpu"] if r["value"] >= threshold]
        return _build_alert_response(alerts, "cpu_pct")

    def mem_alerts(self, date_str, threshold_mb=500):
        ad = self._all_data(date_str)
        if not ad:
            return {"alerts": [], "summary": _empty_alert_summary()}
        # Get total RAM for % calculation
        host_data = self.host(date_str)
        total_ram = host_data.get("total_ram_mb", 0) if host_data else 0
        alerts = []
        for r in ad["mem"]:
            if r["value"] >= threshold_mb:
                entry = dict(r)
                entry["mem_pct"] = round((r["value"] / total_ram) * 100, 2) if total_ram > 0 else 0
                alerts.append(entry)
        return _build_alert_response(alerts, "mem")

    # =================================================================
    # TOP PROCESSES  (latest snapshot from all_*.csv)
    # =================================================================
    def top_processes(self, date_str, metric="MEM"):
        ad = self._all_data(date_str)
        if not ad:
            return {"timestamp": "", "processes": []}
        rows = ad["mem"] if metric == "MEM" else ad["cpu"]
        if not rows:
            return {"timestamp": "", "processes": []}

        # Get last timestamp's data
        last_ts = rows[-1]["timestamp"]
        latest = [r for r in rows if r["timestamp"] == last_ts]
        latest.sort(key=lambda x: -x["value"])

        processes = [
            {
                "name": r["process"],
                "pid": r["pid"],
                "value": round(r["value"], 2),
                "unit": r["unit"],
                "service": r["service"],
            }
            for r in latest[:15]
        ]
        return {"timestamp": last_ts, "processes": processes}

    # =================================================================
    # PROCESS TIMELINE  (top N processes over time from all_*.csv)
    # =================================================================
    def process_timeline(self, date_str, metric="MEM", top_n=8):
        ad = self._all_data(date_str)
        if not ad:
            return {"timestamps": [], "series": []}
        rows = ad["mem"] if metric == "MEM" else ad["cpu"]
        if not rows:
            return {"timestamps": [], "series": []}

        # Collect per-process totals and all timestamps
        process_totals = defaultdict(lambda: [0.0, 0])
        all_timestamps = []
        current_ts = None
        ts_process_val = defaultdict(dict)  # {process: {ts: val}}

        for r in rows:
            name = r["process"]
            ts = r["timestamp"]
            val = r["value"]
            process_totals[name][0] += val
            process_totals[name][1] += 1
            ts_process_val[name][ts] = val
            if ts != current_ts:
                all_timestamps.append(ts)
                current_ts = ts

        # Top N by average value
        avg_sorted = sorted(
            process_totals.items(), key=lambda x: -(x[1][0] / max(x[1][1], 1))
        )
        top_names = [x[0] for x in avg_sorted[:top_n]]

        # Downsample to ~288 points
        if len(all_timestamps) > 300:
            step = max(1, len(all_timestamps) // 288)
            sampled_ts = all_timestamps[::step]
        else:
            sampled_ts = all_timestamps

        series = []
        for name in top_names:
            pdata = ts_process_val[name]
            data_points = [round(pdata.get(ts, 0), 2) for ts in sampled_ts]
            series.append({"name": name, "data": data_points})

        return {"timestamps": sampled_ts, "series": series}


def _empty_alert_summary():
    return {
        "total_count": 0,
        "unique_processes": 0,
        "top_offender": "",
        "process_breakdown": {},
    }


def _build_alert_response(alerts, alert_type):
    process_counts = defaultdict(int)
    for a in alerts:
        process_counts[a["process"]] += 1

    top_offender = max(process_counts, key=process_counts.get) if process_counts else ""
    formatted = []
    for a in alerts:
        entry = {
            "timestamp": a["timestamp"],
            "process": a["process"],
            "pid": a["pid"],
            "service": a["service"],
        }
        if alert_type == "cpu_pct":
            entry["cpu_pct"] = a["value"]
        else:
            entry["mem_mb"] = round(a["value"], 2)
            entry["mem_pct"] = a.get("mem_pct", 0)
        formatted.append(entry)

    return {
        "alerts": formatted,
        "summary": {
            "total_count": len(alerts),
            "unique_processes": len(process_counts),
            "top_offender": top_offender,
            "process_breakdown": dict(
                sorted(process_counts.items(), key=lambda x: -x[1])[:10]
            ),
        },
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
cache = DataCache(CSV_DIR)


class PerfHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        routes = {
            "/": self._serve_html,
            "/api/info": self._api_info,
            "/api/dates": self._api_dates,
            "/api/host": self._api_host,
            "/api/cpu-alerts": self._api_cpu_alerts,
            "/api/mem-alerts": self._api_mem_alerts,
            "/api/top-processes": self._api_top_processes,
            "/api/process-timeline": self._api_process_timeline,
        }

        handler = routes.get(path)
        if handler:
            try:
                handler(params)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self.send_error(404)

    def _send_json(self, data, code=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html(self, _params):
        html_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "perf_dashboard.html"
        )
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _date_param(self, params):
        d = params.get("date", [None])[0]
        if not d:
            d = datetime.now().strftime("%Y-%m-%d")
        return d

    # --- API routes ----------------------------------------------------
    def _api_info(self, params):
        self._send_json({"server_name": cache.get_server_name()})

    def _api_dates(self, params):
        self._send_json({"dates": cache.available_dates()})

    def _api_host(self, params):
        d = self._date_param(params)
        data = cache.host(d)
        self._send_json(
            data
            if data
            else {
                "timestamps": [],
                "cpu_pct": [],
                "used_ram_pct": [],
                "used_ram_mb": [],
                "total_ram_mb": 0,
                "summary": {},
            }
        )

    def _api_cpu_alerts(self, params):
        d = self._date_param(params)
        threshold = float(params.get("threshold", [80])[0])
        data = cache.cpu_alerts(d, threshold)
        self._send_json(data)

    def _api_mem_alerts(self, params):
        d = self._date_param(params)
        threshold_mb = float(params.get("threshold", [500])[0])
        data = cache.mem_alerts(d, threshold_mb)
        self._send_json(data)

    def _api_top_processes(self, params):
        d = self._date_param(params)
        metric = params.get("metric", ["MEM"])[0]
        data = cache.top_processes(d, metric)
        self._send_json(data)

    def _api_process_timeline(self, params):
        d = self._date_param(params)
        metric = params.get("metric", ["MEM"])[0]
        top_n = int(params.get("top", ["8"])[0])
        data = cache.process_timeline(d, metric, top_n)
        self._send_json(data)


# ---------------------------------------------------------------------------
# PowerShell collector management
# ---------------------------------------------------------------------------
_collector_proc = None
COLLECTOR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collector.log")


def start_collector():
    global _collector_proc
    if not os.path.isfile(COLLECTOR_SCRIPT):
        print(f"[WARN] Collector script not found: {COLLECTOR_SCRIPT}")
        print("       Dashboard will work with existing CSV data only.\n")
        return
    
    # Get server from config
    config = load_server_config()
    servers = [s["name"] for s in config.get("servers", []) if s.get("enabled", True)]
    if not servers:
        print("[WARN] No servers configured. Add servers to servers_config.json")
        return
    
    target_server = servers[0]
    cmd = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", COLLECTOR_SCRIPT,
        "-Server", target_server,
    ]
    print(f"[OK]  Launching collector: {target_server}")
    log_fh = open(COLLECTOR_LOG, "w", encoding="utf-8")
    _collector_proc = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    print(f"[OK]  Collector PID: {_collector_proc.pid}")
    print(f"[OK]  Collector log: {COLLECTOR_LOG}\n")


def stop_collector():
    global _collector_proc
    if _collector_proc and _collector_proc.poll() is None:
        print("Stopping collector...")
        _collector_proc.terminate()
        try:
            _collector_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _collector_proc.kill()
        print("Collector stopped.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Server Performance Tracker ===")
    print(f"CSV directory : {CSV_DIR}")
    print(f"Server name   : {cache.get_server_name()}")
    print(f"Available dates: {', '.join(cache.available_dates())}")
    print(f"Local URL     : http://localhost:{PORT}")
    print(f"Network URL   : http://10.11.33.183:{PORT}")
    print("\nShare the Network URL with your team to access the dashboard")
    print("Press Ctrl+C to stop.\n")

    start_collector()

    server = http.server.HTTPServer(("0.0.0.0", PORT), PerfHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_collector()
        server.server_close()
        print("Done.")
