# Same base — consistency matters more than a few MB here
FROM python:3.12-slim

WORKDIR /app

# Install only what the frontend needs — much lighter than full requirements.txt
# (no torch, no chromadb, no sentence-transformers)
RUN pip install --no-cache-dir \
    streamlit==1.38.0 \
    requests==2.34.2 \
    python-dotenv==1.2.2

# Copy only the frontend source code
COPY frontend/ ./frontend/

EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", \
     "--server.port", "8501", \
     "--server.address", "0.0.0.0", \
     "--server.headless", "true"]