FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway provides PORT - use shell form to expand variable
CMD uvicorn api.main:app --host 0.0.0.0 --port $PORT
