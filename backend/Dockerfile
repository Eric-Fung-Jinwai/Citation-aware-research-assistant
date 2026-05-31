# Start from official Python 3.12 slim image (arm64-compatible)
FROM python:3.12-slim

# All commands from here run inside /app inside the container
WORKDIR /app

# Install dependencies first (separate layer so Docker caches it —
# rebuilds skip this step if requirements.txt hasn't changed)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the backend source code into the image
# (.dockerignore prevents secrets and junk from leaking in)
COPY backend/ ./backend/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]