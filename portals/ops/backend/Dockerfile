FROM python:3.11-slim

WORKDIR /app

# Install deps first (layer-cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create audit log directory
RUN mkdir -p /paperclip/.audit

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
