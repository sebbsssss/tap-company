FROM python:3.12-slim

WORKDIR /app

COPY occupancy/ ./occupancy/
COPY dashboard/ ./dashboard/
COPY occupancy-dashboard.html ./

# No external dependencies — pure stdlib
# Fly.io injects PORT; OCCUPANCY_PORT is the app's own override
ENV OCCUPANCY_PORT=8080

EXPOSE 8080

CMD ["python", "-m", "occupancy"]
