"""
Stdlib HTTP server for the occupancy API.

Routing table:
  GET  /api/occupancy/summary            → handle_summary
  GET  /api/occupancy/daily              → handle_daily
  GET  /api/occupancy/properties         → handle_properties
  GET  /api/occupancy/units/<propertyId> → handle_units
  GET  /api/occupancy/data-quality       → handle_data_quality
  GET  /api/occupancy/export/csv         → handle_export_csv
  GET  /api/occupancy/export/pdf-data    → handle_export_pdf_data
  GET  /api/occupancy/settings/target    → handle_get_targets
  PUT  /api/occupancy/settings/target    → handle_put_targets

Data is fetched from the CRM once per request (suitable for low-volume dashboards;
add an in-process TTL cache if needed for higher load).

Health check: GET /healthz
"""

from __future__ import annotations

import http.server
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from occupancy import api as handlers
from occupancy.config import OccupancyConfig, load as load_config
from occupancy.crm_client import CRMClient, CRMAPIError, CRMConfigError, load_from_fixtures
from occupancy.models import OccupancyData
from occupancy.target_store import TargetStore


_ROUTES = [
    ("GET",  r"^/$",                                  "dashboard"),
    ("GET",  r"^/dashboard/?$",                       "dashboard"),
    ("GET",  r"^/dashboard/(.+)$",                    "dashboard_static"),
    ("GET",  r"^/api/occupancy/summary$",             "summary"),
    ("GET",  r"^/api/occupancy/daily$",               "daily"),
    ("GET",  r"^/api/occupancy/properties$",          "properties"),
    ("GET",  r"^/api/occupancy/units-monthly$",       "units_monthly"),
    ("GET",  r"^/api/occupancy/units/([^/]+)$",       "units"),
    ("GET",  r"^/api/occupancy/data-quality$",        "data_quality"),
    ("GET",  r"^/api/occupancy/export/csv$",          "export_csv"),
    ("GET",  r"^/api/occupancy/export/pdf-data$",     "export_pdf_data"),
    ("GET",  r"^/api/occupancy/settings/target$",     "get_targets"),
    ("PUT",  r"^/api/occupancy/settings/target$",     "put_targets"),
    ("GET",  r"^/healthz$",                           "healthz"),
]

_DASHBOARD_DIR  = Path(__file__).parent.parent / "dashboard"
_DASHBOARD_HTML = _DASHBOARD_DIR / "index.html"
_DASHBOARD_HTML_LEGACY = Path(__file__).parent.parent / "occupancy-dashboard.html"

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".jsx":  "application/javascript; charset=utf-8",
    ".ttf":  "font/ttf",
    ".woff2": "font/woff2",
    ".json": "application/json",
    ".ico":  "image/x-icon",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
}

_COMPILED = [(m, re.compile(pat), name) for m, pat, name in _ROUTES]


def _build_handler(cfg: OccupancyConfig, fixtures_path: str | None) -> type:
    store = TargetStore(cfg.target_db_path)

    def _get_data() -> OccupancyData:
        if fixtures_path:
            return load_from_fixtures(fixtures_path)
        client = CRMClient(cfg)
        return client.fetch_all()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            ts = datetime.now(tz=timezone.utc).isoformat()
            print(json.dumps({
                "level": "info",
                "ts": ts,
                "method": self.command,
                "path": self.path,
                "msg": fmt % args,
            }), file=sys.stderr)

        def _send(self, status: int, headers: dict, body: bytes) -> None:
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def _json_error(self, msg: str, status: int = 400) -> None:
            body = json.dumps({"error": msg}).encode()
            self._send(status, {"Content-Type": "application/json"}, body)

        def _params(self) -> dict:
            parsed = urllib.parse.urlparse(self.path)
            return dict(urllib.parse.parse_qsl(parsed.query))

        def _path_only(self) -> str:
            return urllib.parse.urlparse(self.path).path

        def _route(self) -> tuple[str | None, re.Match | None]:
            path = self._path_only()
            for method, pattern, name in _COMPILED:
                if method == self.command:
                    m = pattern.match(path)
                    if m:
                        return name, m
            return None, None

        def _handle_request(self, body: bytes = b"") -> None:
            name, match = self._route()
            if name is None:
                self._json_error("Not found", 404)
                return

            if name == "healthz":
                self._send(200, {"Content-Type": "application/json"}, b'{"status":"ok"}')
                return

            if name == "dashboard":
                # Redirect /dashboard → /dashboard/ so relative asset paths resolve correctly.
                if not self._path_only().endswith("/"):
                    self.send_response(301)
                    self.send_header("Location", "/dashboard/")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                html_path = _DASHBOARD_HTML if _DASHBOARD_HTML.exists() else _DASHBOARD_HTML_LEGACY
                if html_path.exists():
                    body = html_path.read_bytes()
                    self._send(200, {"Content-Type": "text/html; charset=utf-8"}, body)
                else:
                    self._json_error("Dashboard not found", 404)
                return

            if name == "dashboard_static":
                rel = match.group(1)
                # Prevent path traversal
                target = (_DASHBOARD_DIR / rel).resolve()
                if not str(target).startswith(str(_DASHBOARD_DIR.resolve())):
                    self._json_error("Forbidden", 403)
                    return
                if target.is_file():
                    ct = _MIME.get(target.suffix, "application/octet-stream")
                    self._send(200, {"Content-Type": ct}, target.read_bytes())
                else:
                    self._json_error("Not found", 404)
                return

            try:
                data = _get_data()
            except (CRMConfigError, CRMAPIError) as e:
                self._json_error(f"CRM error: {e}", 502)
                return
            except Exception as e:
                self._json_error(f"Internal error: {e}", 500)
                return

            params = self._params()

            try:
                if name == "summary":
                    status, headers, resp = handlers.handle_summary(params, data, store)
                elif name == "daily":
                    status, headers, resp = handlers.handle_daily(params, data, store)
                elif name == "properties":
                    status, headers, resp = handlers.handle_properties(params, data, store)
                elif name == "units_monthly":
                    status, headers, resp = handlers.handle_units_monthly(params, data, store)
                elif name == "units":
                    property_id = match.group(1)
                    status, headers, resp = handlers.handle_units(property_id, params, data, store)
                elif name == "data_quality":
                    status, headers, resp = handlers.handle_data_quality(params, data, store)
                elif name == "export_csv":
                    status, headers, resp = handlers.handle_export_csv(params, data, store)
                elif name == "export_pdf_data":
                    status, headers, resp = handlers.handle_export_pdf_data(params, data, store)
                elif name == "get_targets":
                    status, headers, resp = handlers.handle_get_targets(params, data, store)
                elif name == "put_targets":
                    try:
                        req_body = json.loads(body.decode()) if body else {}
                    except json.JSONDecodeError:
                        self._json_error("Invalid JSON body")
                        return
                    status, headers, resp = handlers.handle_put_targets(req_body, data, store)
                else:
                    self._json_error("Not found", 404)
                    return
            except Exception as e:
                self._json_error(f"Handler error: {e}", 500)
                return

            self._send(status, headers, resp)

        def do_GET(self) -> None:
            self._handle_request()

        def do_PUT(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b""
            self._handle_request(body)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

    return Handler


def run(port: int, fixtures_path: str | None = None) -> None:
    cfg = load_config()
    handler_class = _build_handler(cfg, fixtures_path)
    server = http.server.HTTPServer(("0.0.0.0", port), handler_class)
    mode = "fixtures" if fixtures_path else "live CRM"
    print(json.dumps({
        "level": "info",
        "msg": f"Occupancy API listening on port {port} ({mode})",
        "ts": datetime.now(tz=timezone.utc).isoformat(),
    }), file=sys.stderr)
    server.serve_forever()
