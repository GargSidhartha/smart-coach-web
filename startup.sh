#!/bin/bash
# Create necessary directories
mkdir -p uploads
mkdir -p results
mkdir -p models

# Download model file from external source
if [ ! -f "models/best.pt" ]; then
  echo "Downloading YOLO model file..."
  # Using the correct format for Google Drive direct download
  # The file ID is extracted from your URL
  FILE_ID="1O3n7SGI83vFJ50biXA5biEvaOvbmIIPD"
  curl -L "https://drive.google.com/uc?export=download&id=${FILE_ID}" -o models/best.pt
  echo "Model download complete!"
fi

# Set the PORT environment variable for Render if not already set
export PORT=${PORT:-5000}
echo "Application will listen on port: $PORT"

# Start the application (these are handled by Render's start command)
# exec gunicorn wsgi:app  # For web service
# exec celery -A celery_worker.celery worker --loglevel=info  # For worker