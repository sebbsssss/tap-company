"""
Runtime configuration for the occupancy API.
All values read from environment variables.

Required env vars:
  CRM_STAFF_API_KEY   — x-api-key header value (post-May-2026 auth)

Optional env vars:
  CRM_API_BASE                     — CRM base URL (default: https://crm-api.theassemblyplace.com)
  OCCUPANCY_TARGET_DB              — path to SQLite file for target storage (default: occupancy_targets.db)
  OCCUPANCY_PORT                   — HTTP port for the API server (default: 8080)
  OCCUPANCY_ROOM_AVAILABILITY_MODULE — CRM endpoint for room availability data
                                       (default: com/dashboard/room_availability)
  OCCUPANCY_EXCEL_PATH             — path to cleaned occupancy Excel file
                                     (default: /data/occupancy.xlsx on Fly, data/occupancy.xlsx locally)
  ADMIN_API_TOKEN                  — bearer token for POST /api/admin/upload-occupancy
"""

import os
from dataclasses import dataclass

_DEFAULT_CRM_BASE = "https://crm-api.theassemblyplace.com"
_DEFAULT_EXCEL_PATH = "/data/occupancy.xlsx" if os.path.isdir("/data") else "data/occupancy.xlsx"


@dataclass(frozen=True)
class OccupancyConfig:
    crm_api_base: str
    crm_api_key: str
    target_db_path: str
    port: int
    room_availability_module: str
    excel_path: str
    admin_api_token: str


def load() -> OccupancyConfig:
    return OccupancyConfig(
        crm_api_base=os.environ.get("CRM_API_BASE", _DEFAULT_CRM_BASE),
        crm_api_key=os.environ.get("CRM_STAFF_API_KEY", ""),
        target_db_path=os.environ.get("OCCUPANCY_TARGET_DB", "occupancy_targets.db"),
        port=int(os.environ.get("OCCUPANCY_PORT", "8080")),
        room_availability_module=os.environ.get(
            "OCCUPANCY_ROOM_AVAILABILITY_MODULE",
            "com/dashboard/room_availability",
        ),
        excel_path=os.environ.get("OCCUPANCY_EXCEL_PATH", _DEFAULT_EXCEL_PATH),
        admin_api_token=os.environ.get("ADMIN_API_TOKEN", ""),
    )
