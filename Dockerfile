# Step 1: Build the React frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Step 2: Run the FastAPI backend + serve frontend
FROM python:3.13-slim
WORKDIR /app

# Install Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Copy built frontend into backend/static
COPY --from=frontend /app/frontend/dist ./static

# Run on Railway's assigned $PORT (fallback to 8000 locally)
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
