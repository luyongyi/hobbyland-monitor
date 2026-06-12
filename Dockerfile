# ---- Stage 1: Build Vue frontend ----
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Use China mirror for faster builds
RUN npm config set registry https://registry.npmmirror.com

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build
# Output: /app/frontend/dist/

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY src/ src/
COPY config/ config/

# Copy built frontend into static/ for FastAPI to serve
COPY --from=frontend-builder /app/frontend/dist /app/static

# Config and data are mounted via docker-compose
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
