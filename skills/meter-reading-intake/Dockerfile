FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ ./scripts/

# Run from scripts/ so module imports resolve without a package prefix
WORKDIR /app/scripts

CMD ["uvicorn", "meter_intake:app", "--host", "0.0.0.0", "--port", "8080"]
