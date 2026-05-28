import os
from occupancy.server import run

port = int(os.environ.get("PORT") or os.environ.get("OCCUPANCY_PORT") or 8080)
run(port)
