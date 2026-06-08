FROM python:3.12-slim

WORKDIR /app

# System deps: nginx for routing between occupancy + ops-portal
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx && \
    rm -rf /var/lib/apt/lists/*

# Install ops-portal Python deps first (layer-cache friendly)
COPY portals/ops/backend/requirements.txt ./portals/ops/backend/requirements.txt
RUN pip install --no-cache-dir -r portals/ops/backend/requirements.txt

# Install honcho (Procfile process manager) and remove pytest from prod
RUN pip install --no-cache-dir honcho

# Copy application code
COPY occupancy/ ./occupancy/
COPY dashboard/ ./dashboard/
COPY occupancy-dashboard.html ./
COPY portals/ops/backend/ ./portals/ops/backend/
COPY portals/ops/frontend/ ./portals/ops/backend/frontend/
COPY nginx.conf /etc/nginx/nginx.conf

# Procfile — honcho starts all three services
COPY Procfile ./Procfile

# Persistent data for ops-portal (audit log + session DB)
RUN mkdir -p /data/audit

ENV OCCUPANCY_PORT=8082

EXPOSE 8080

CMD ["honcho", "start"]
