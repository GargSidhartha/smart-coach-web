import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'you-should-change-this')
    
    # Model and data paths - define these first so we can use them later
    MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'best.pt')
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'uploads'))
    RESULT_FOLDER = os.environ.get('RESULT_FOLDER', os.path.join(os.path.dirname(__file__), 'results'))
    
    # For Heroku, use CloudAMQP if available (from CLOUDAMQP_URL env var)
    # Otherwise fall back to local RabbitMQ for development
    CLOUDAMQP_URL = os.environ.get('CLOUDAMQP_URL')
    
    if CLOUDAMQP_URL:
        # On Heroku, use CloudAMQP for broker
        CELERY_BROKER_URL = CLOUDAMQP_URL
        CELERY_RESULT_BACKEND = 'rpc://'  # RPC backend works well with RabbitMQ
    else:
        # Local development fallback
        CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//')
        CELERY_RESULT_BACKEND = 'rpc://'

    # Optional: Cloud storage configuration (examples)
    # USE_CLOUD_STORAGE = os.environ.get('USE_CLOUD_STORAGE', 'False').lower() in ('true', '1', 't')
    # S3_BUCKET = os.environ.get('S3_BUCKET')
    # GCS_BUCKET = os.environ.get('GCS_BUCKET')
    # AZURE_CONTAINER = os.environ.get('AZURE_CONTAINER')

    # Ensure required directories exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(RESULT_FOLDER, exist_ok=True)
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    # Add other configurations as needed