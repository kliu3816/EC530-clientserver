# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY . .

CMD ["python", "server.py"]  # or client.py, depending on which service
