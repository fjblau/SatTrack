#!/bin/bash

# Start script for UNOOSA Registry application
# Starts MongoDB (Docker), Python API backend, and React frontend

set -e

echo "🚀 Starting UNOOSA Registry..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker Desktop from https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

# Kill any existing processes on ports 8000 and 3000
echo "Cleaning up old processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
sleep 1

# Start MongoDB via Docker Compose
echo "🗄️  Starting MongoDB (Docker) on port 27018..."
cd "$SCRIPT_DIR"
docker compose up -d mongodb

# Wait for MongoDB to be healthy
echo "Waiting for MongoDB to be ready..."
for i in {1..30}; do
    if docker compose exec -T mongodb mongosh --eval "db.adminCommand('ping')" --quiet &> /dev/null; then
        echo "✅ MongoDB is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ MongoDB failed to start within 30 seconds"
        docker compose logs mongodb
        docker compose down
        exit 1
    fi
    sleep 1
done

# Start the API server
echo "📡 Starting API server on http://127.0.0.1:8000..."
cd "$SCRIPT_DIR"
python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 &
API_PID=$!
sleep 2

# Verify API is running
if ! kill -0 $API_PID 2>/dev/null; then
  echo "❌ Failed to start API server"
  exit 1
fi
echo "✅ API server running (PID: $API_PID)"

# Start the React development server
echo "⚛️  Starting React dev server on http://localhost:3000..."
cd "$SCRIPT_DIR/react-app"
npm run dev &
REACT_PID=$!
sleep 3

# Verify React is running
if ! kill -0 $REACT_PID 2>/dev/null; then
  echo "❌ Failed to start React dev server"
  kill $API_PID 2>/dev/null || true
  exit 1
fi
echo "✅ React dev server running (PID: $REACT_PID)"

echo ""
echo "=========================================="
echo "🎉 All services started successfully!"
echo "=========================================="
echo ""
echo "Access the app at: http://localhost:3000"
echo ""
echo "MongoDB: localhost:27018"
echo "API server: http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Handle Ctrl+C to stop all services including Docker containers
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $API_PID $REACT_PID 2>/dev/null || true
    cd "$SCRIPT_DIR"
    docker compose down
    exit 0
}

trap cleanup SIGINT

# Wait for both processes
wait
