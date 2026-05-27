"""
Runtime configuration for the occupancy API.
All values read from environment variables.

Required env vars:
  CRM_API_BASE        — e.g. https://crm.theassemblyplace.com
  CRM_STAFF_API_KEY   — x-api-key header value (post-May-2026 auth)

Optional env vars:
  OCCUPANCY_TARGET_DB              — path to SQLite file for target storage (default: occupancy_targets.db)
  OCCUPANCY_PORT                   — HTTP port for the API server (default: 8080)
  OCCUPANCY_ROOM_AVAILABILITY_MODULE — CRM endpoint for room availability data
                                       (default: com/dashboard/room_availability)
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OccupancyConfig:
    crm_api_base: str
    crm_api_key: str
    target_db_path: str
    port: int
    room_availability_module: str


def load() -> OccupancyConfig:
    return OccupancyConfig(
        crm_api_base=os.environ.get("CRM_API_BASE", ""),
        crm_api_key=os.environ.get("CRM_STAFF_API_KEY", ""),
        target_db_path=os.environ.get("OCCUPANCY_TARGET_DB", "occupancy_targets.db"),
        port=int(os.environ.get("OCCUPANCY_PORT", "8080")),
        room_availability_module=os.environ.get(
            "OCCUPANCY_ROOM_AVAILABILITY_MODULE",
            "com/dashboard/room_availability",
        ),
    )
