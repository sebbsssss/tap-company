"""
Runtime configuration for the occupancy API.
All values read from environment variables.

Required env vars:
  CRM_API_BASE        — e.g. https://crm.theassemblyplace.com
  CRM_STAFF_API_KEY   — x-api-key header value (post-May-2026 auth)

Optional env vars:
  OCCUPANCY_TARGET_DB      — path to SQLite file for target storage (default: occupancy_targets.db)
  OCCUPANCY_PORT           — HTTP port for the API server (default: 8080)
  OCCUPANCY_PROPERTY_MODULE — CRM module name for properties (default: com/properties)
  OCCUPANCY_UNIT_MODULE     — CRM module name for units (default: com/units)
  OCCUPANCY_TENANT_MODULE   — CRM module name for tenants (default: com/tenants)
  OCCUPANCY_LEASE_MODULE    — CRM module name for leases (default: com/leases)
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OccupancyConfig:
    crm_api_base: str
    crm_api_key: str
    target_db_path: str
    port: int
    property_module: str
    unit_module: str
    tenant_module: str
    lease_module: str


def load() -> OccupancyConfig:
    return OccupancyConfig(
        crm_api_base=os.environ.get("CRM_API_BASE", ""),
        crm_api_key=os.environ.get("CRM_STAFF_API_KEY", ""),
        target_db_path=os.environ.get("OCCUPANCY_TARGET_DB", "occupancy_targets.db"),
        port=int(os.environ.get("OCCUPANCY_PORT", "8080")),
        property_module=os.environ.get("OCCUPANCY_PROPERTY_MODULE", "com/properties"),
        unit_module=os.environ.get("OCCUPANCY_UNIT_MODULE", "com/units"),
        tenant_module=os.environ.get("OCCUPANCY_TENANT_MODULE", "com/tenants"),
        lease_module=os.environ.get("OCCUPANCY_LEASE_MODULE", "com/leases"),
    )
