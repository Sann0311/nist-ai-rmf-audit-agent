#!/bin/bash

# Script to restart the frontend with the fixed version
echo "Stopping current containers..."
cd /c/Users/bhala/Downloads/agent_skeleton/agent_skeleton
docker-compose down

echo "Starting with fixed frontend..."
docker-compose up -d frontend

echo "Frontend restarted with fixes. Access at http://localhost:8501"
echo "The debug mode checkbox is now in the sidebar and should not cause duplicate key errors."
