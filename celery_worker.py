import os
from celery import Celery
import traceback

# Import the actual analysis function
# If this fails, the worker will not start and the error will be shown immediately.
from processing.video_analyzer import analyze_video


# Initialize Celery
# Read broker/backend URLs from environment variables defined in Config
# Default to localhost RabbitMQ if not set
celery_app = Celery(
    'foot_update_tasks', # Give the celery app a name
    broker=os.environ.get('CELERY_BROKER_URL', 'amqp://guest:guest@localhost:5672//'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'rpc://') # Consider Redis/DB for production
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    # Optional: Improve reliability/visibility
    task_track_started=True,
    # task_acks_late=True, # If tasks are idempotent and can be retried
    # worker_prefetch_multiplier=1, # If tasks are long-running
)

@celery_app.task(bind=True, name='process_video_task') # Add explicit task name
def process_video_task(self, input_path, output_video_filename, output_stats_filename, model_path):
    """Celery task to process the uploaded video using video_analyzer.analyze_video."""
    # Get result folder from environment (consistent with Flask config)
    result_folder = os.environ.get('RESULT_FOLDER', os.path.abspath(os.path.join(os.path.dirname(__file__), 'results')))
    os.makedirs(result_folder, exist_ok=True) # Ensure it exists
    
    output_video_path = os.path.join(result_folder, output_video_filename)
    output_stats_path = os.path.join(result_folder, output_stats_filename)

    try:
        print(f"[Task {self.request.id}] Received task: analyze {input_path}")
        # Update task state to STARTED with progress info
        self.update_state(state='STARTED', meta={'current': 0, 'total': 100, 'status': 'Processing starting...'})

        # --- Call the actual processing logic --- 
        # Pass the task instance (self) to analyze_video for progress updates
        results = analyze_video(
            input_path=input_path,
            output_video_path=output_video_path, 
            output_stats_path=output_stats_path, 
            model_path=model_path,
            task=self # Pass task instance
        )
        # --- Processing finished --- 

        print(f"[Task {self.request.id}] Processing successful. Results: {results}")
        # Update task state to SUCCESS
        # The analyze_video function should return the relative paths
        final_status = {
            'current': 100, 
            'total': 100, 
            'status': 'Processing complete!',
            'result_video': results.get('video_path'), # Use relative path from result dict
            'result_stats': results.get('stats_path')  # Use relative path from result dict
        }
        self.update_state(state='SUCCESS', meta=final_status)
        return final_status # Return the final status dictionary

    except FileNotFoundError as e:
        print(f"[Task {self.request.id}] ERROR: File not found - {e}")
        error_meta = {
            'exc_type': type(e).__name__,
            'exc_message': str(e),
            'status': f'Error: Input file or model not found.'
        }
        self.update_state(state='FAILURE', meta=error_meta)
        # Optionally re-raise if you want Celery's default failure handling
        # raise # Or return the error meta for custom handling in frontend
        return error_meta

    except Exception as e:
        print(f"[Task {self.request.id}] PROCESSING FAILED: {e}")
        print(traceback.format_exc()) # Log the full traceback
        error_meta = {
            'exc_type': type(e).__name__,
            'exc_message': str(e),
            'status': f'Processing failed due to an internal error: {type(e).__name__}'
            # 'traceback': traceback.format_exc() # Avoid sending full tracebacks to client
        }
        self.update_state(state='FAILURE', meta=error_meta)
        # raise # Or return the error meta
        return error_meta

# Rename the celery instance variable for clarity if needed, 
# Flask app typically imports the task directly.
celery = celery_app

# Placeholder for the actual video processing logic
# This function will be replaced by the logic from processing/video_analyzer.py
def perform_video_analysis(input_path, output_video_path, output_stats_path, model_path):
    print(f"Starting analysis for {input_path}")
    print(f"Using model: {model_path}")
    # Simulate processing time
    time.sleep(10)
    # In reality, call your video processing function here
    # Example: analysis_results = analyze_video(input_path, output_video_path, model_path)
    # Simulate creating output files
    with open(output_video_path, 'w') as f:
        f.write("Simulated processed video data.")
    simulated_stats = {'possession': {'Team A': 55, 'Team B': 45}, 'offsides': 3}
    with open(output_stats_path, 'w') as f:
        import json
        json.dump(simulated_stats, f)
    print(f"Finished analysis. Output video: {output_video_path}, Stats: {output_stats_path}")
    return {"video_path": output_video_path, "stats_path": output_stats_path}

# Optional: Import your actual processing function if it's ready
# try:
#     from processing.video_analyzer import analyze_video
# except ImportError:
#     print("Warning: processing.video_analyzer not found. Using placeholder.")
#     analyze_video = lambda *args, **kwargs: {} # Simple placeholder 