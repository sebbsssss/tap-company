nginx: nginx -g 'daemon off;'
occupancy: python -m occupancy
portal: cd portals/ops/backend && uvicorn main:app --host 127.0.0.1 --port 8001 --workers 1
