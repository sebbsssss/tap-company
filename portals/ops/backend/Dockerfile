FROM python:3.11-slim

WORKDIR /app

# Build context is portals/ops/ — both backend/ and frontend/ are available.
# Install deps first (layer-cache friendly)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ .

# Copy frontend static files so the backend can serve them at /
COPY frontend/ ./frontend/

# Persistent data directory for audit log + session DB (mounted as Fly volume)
RUN mkdir -p /data/audit

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
