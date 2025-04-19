#!/bin/bash
# Create necessary directories
mkdir -p uploads
mkdir -p results
mkdir -p models

# Download model file from external source
if [ ! -f "models/best.pt" ]; then
  echo "Downloading YOLO model file..."
  # IMPORTANT: Replace this URL with your actual model download link
  # For Google Drive, you may need a special command like:
  # curl -L "https://drive.google.com/uc?export=download&id=YOUR_FILE_ID" -o models/best.pt
  #
  # For Hugging Face:
  # curl -L "https://huggingface.co/YOUR_USERNAME/YOUR_MODEL_REPO/resolve/main/best.pt" -o models/best.pt
  #
  # For Dropbox:
  # curl -L "https://www.dropbox.com/s/YOUR_FILE_PATH?dl=1" -o models/best.pt
  
  curl -L "YOUR_MODEL_DOWNLOAD_URL" -o models/best.pt
  echo "Model download complete!"
fi

# Start the application (these are handled by Render's start command)
# exec gunicorn wsgi:app  # For web service
# exec celery -A celery_worker.celery worker --loglevel=info  # For worker