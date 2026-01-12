#!/bin/bash

case "$1" in
  start)
    if docker ps -a --format '{{.Names}}' | grep -q '^sattrack$'; then
      echo "Starting sattrack container..."
      docker start sattrack
      echo "✓ MongoDB started on port 27019"
    else
      echo "Creating sattrack container..."
      docker run -d \
        --name sattrack \
        -p 27019:27017 \
        -v import-data-from-other-instance-5b0d_mongodb_data:/data/db \
        --restart unless-stopped \
        mongo:7.0
      sleep 3
      echo "✓ MongoDB created and started on port 27019"
    fi
    ;;
  stop)
    echo "Stopping sattrack container..."
    docker stop sattrack
    ;;
  status)
    docker ps --filter "name=sattrack" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
