#!/bin/bash

# Start script for UNOOSA Registry application
# Starts ArangoDB (Docker), Python API backend, and React frontend

set -e

echo "🚀 Starting UNOOSA Registry..."
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if venv exists but is broken (directory exists but Python binary doesn't)
if [ -d "venv" ] && [ ! -f "venv/bin/python" ]; then
    echo "⚠️  Found broken venv directory (missing Python binary), removing..."
    rm -rf venv
fi

# Check if venv has required packages installed
if [ -f "venv/bin/python" ]; then
    if ! venv/bin/python -c "import fastapi" 2>/dev/null; then
        echo "⚠️  Found venv with missing packages, recreating..."
        rm -rf venv
    fi
fi

# Setup Python virtual environment if it doesn't exist
if [ ! -f "venv/bin/python" ]; then
    echo "📦 Creating Python virtual environment..."
    
    # Try to find Python 3.11 or higher
    PYTHON_CMD=""
    for py in python3.13 python3.12 python3.11 python3; do
        if command -v $py &> /dev/null; then
            VERSION=$($py -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            MAJOR=$(echo $VERSION | cut -d. -f1)
            MINOR=$(echo $VERSION | cut -d. -f2)
            if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ]; then
                PYTHON_CMD=$py
                echo "Found $py (version $VERSION)"
                break
            fi
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        echo "❌ Error: Python 3.11 or higher is required"
        echo "Please install Python 3.11+ and try again"
        exit 1
    fi
    
    $PYTHON_CMD -m venv venv
    echo "✅ Virtual environment created"
    
    echo "📥 Installing Python dependencies..."
    venv/bin/pip install --upgrade pip setuptools wheel > /dev/null
    venv/bin/pip install -r requirements.txt
    echo "✅ Dependencies installed"
fi

# Use Python from virtual environment
PYTHON="$SCRIPT_DIR/venv/bin/python"

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

# Start ArangoDB (check if container exists first)
echo "🗄️  Starting ArangoDB (Docker) on port 8529..."
cd "$SCRIPT_DIR"

if docker ps -a --format '{{.Names}}' | grep -q '^sattrack$'; then
    echo "Starting existing sattrack container..."
    docker start sattrack 2>/dev/null || true
else
    echo "Creating new sattrack container..."
    docker run -d \
        --name sattrack \
        -p 8529:8529 \
        -e ARANGO_ROOT_PASSWORD=kessler_dev_password \
        -v sattrack_arangodb_data:/var/lib/arangodb3 \
        --restart unless-stopped \
        arangodb/enterprise:3.12.7.1
fi

# Wait for ArangoDB to be healthy
echo "Waiting for ArangoDB to be ready..."
for i in {1..30}; do
    if curl -s -u root:kessler_dev_password http://localhost:8529/_api/version &> /dev/null; then
        echo "✅ ArangoDB is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ ArangoDB failed to start within 30 seconds"
        docker logs sattrack
        exit 1
    fi
    sleep 1
done

# Run startup validation (optional - set SKIP_VALIDATION=1 to skip)
if [ -z "$SKIP_VALIDATION" ]; then
    echo "🔍 Validating startup requirements..."
    if ! $PYTHON test_startup.py; then
        echo ""
        echo "💡 Tip: Set SKIP_VALIDATION=1 to bypass validation"
        exit 1
    fi
    echo ""
fi

# Start the API server
echo "📡 Starting API server on http://127.0.0.1:8000..."
cd "$SCRIPT_DIR"
$PYTHON -m uvicorn api:app --host 127.0.0.1 --port 8000 &
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
echo "ArangoDB: http://localhost:8529"
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
    docker stop sattrack 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT

# Wait for both processes
wait
