#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

case "$1" in
    start)
        echo "Starting MongoDB..."
        docker compose up -d mongodb
        echo "Waiting for MongoDB to be ready..."
        for i in {1..30}; do
            if docker compose exec -T mongodb mongosh --eval "db.adminCommand('ping')" --quiet &> /dev/null; then
                echo "✅ MongoDB is ready on port 27019"
                exit 0
            fi
            sleep 1
        done
        echo "❌ MongoDB failed to start within 30 seconds"
        exit 1
        ;;
    
    stop)
        echo "Stopping MongoDB..."
        docker compose down
        echo "✅ MongoDB stopped"
        ;;
    
    reset)
        echo "⚠️  This will delete all data in MongoDB!"
        read -p "Are you sure? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            echo "Stopping MongoDB and removing volumes..."
            docker compose down -v
            echo "✅ MongoDB data reset. Run './scripts/mongodb.sh start' to start fresh."
        else
            echo "Reset cancelled."
        fi
        ;;
    
    logs)
        echo "Showing MongoDB logs (Ctrl+C to exit)..."
        docker compose logs -f mongodb
        ;;
    
    shell)
        echo "Opening MongoDB shell (mongosh)..."
        echo "Connected to: localhost:27019/kessler"
        docker compose exec mongodb mongosh kessler
        ;;
    
    status)
        echo "MongoDB status:"
        docker compose ps mongodb
        ;;
    
    *)
        echo "MongoDB Helper Script"
        echo ""
        echo "Usage: $0 {start|stop|reset|logs|shell|status}"
        echo ""
        echo "Commands:"
        echo "  start   - Start MongoDB container"
        echo "  stop    - Stop MongoDB container"
        echo "  reset   - Stop MongoDB and delete all data (requires confirmation)"
        echo "  logs    - Show MongoDB logs"
        echo "  shell   - Open MongoDB shell (mongosh)"
        echo "  status  - Show MongoDB container status"
        echo ""
        exit 1
        ;;
esac
