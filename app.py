import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory, url_for
from werkzeug.utils import secure_filename
from celery.result import AsyncResult

# Import Celery task and app instance
from celery_worker import celery, process_video_task
from config import Config

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance folder exists (if needed, though config handles main folders)
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # --- Routes --- 
    @app.route('/')
    def index():
        """Serves the main HTML page."""
        return render_template('index.html')

    @app.route('/upload', methods=['POST'])
    def upload_video():
        """Handles video upload and starts the Celery task."""
        if 'video' not in request.files:
            return jsonify({"error": "No video file part"}), 400
        file = request.files['video']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            # Generate unique names for stored/processed files
            unique_id = uuid.uuid4().hex
            _, ext = os.path.splitext(original_filename)
            input_filename = f"{unique_id}{ext}"
            output_video_filename = f"{unique_id}_processed.mp4" # Standardize output format
            output_stats_filename = f"{unique_id}_stats.json"

            input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
            file.save(input_path)

            # Start Celery task
            task = process_video_task.delay(
                input_path=input_path,
                output_video_filename=output_video_filename,
                output_stats_filename=output_stats_filename,
                model_path=app.config['MODEL_PATH']
            )

            return jsonify({"task_id": task.id}), 202 # Accepted
        else:
            return jsonify({"error": "Invalid file type"}), 400

    @app.route('/status/<task_id>')
    def task_status(task_id):
        """Checks the status of a Celery task."""
        task = process_video_task.AsyncResult(task_id)
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Pending...'
            }
        elif task.state != 'FAILURE':
            response = {
                'state': task.state,
                'status': task.info.get('status', ''),
            }
            if 'result_video' in task.info:
                response['result_video'] = url_for('get_result_file', filename=os.path.basename(task.info['result_video']), _external=True)
                response['result_stats'] = url_for('get_result_file', filename=os.path.basename(task.info['result_stats']), _external=True)

        else:
            # Task failed
            response = {
                'state': task.state,
                'status': str(task.info), # Exception info
            }
        return jsonify(response)

    @app.route('/results/<filename>')
    def get_result_file(filename):
        """Serves processed video or stats files from the result folder."""
        # SECURITY NOTE: In production, NEVER serve files directly like this
        # from a user-writable directory without stringent checks.
        # Prefer serving from a dedicated static file server (Nginx) or cloud storage.
        safe_filename = secure_filename(filename)
        
        # Set correct MIME type based on file extension
        mime_type = None
        if filename.lower().endswith('.mp4'):
            mime_type = 'video/mp4'
        elif filename.lower().endswith('.avi'):
            mime_type = 'video/x-msvideo'
        elif filename.lower().endswith('.webm'):
            mime_type = 'video/webm'
        elif filename.lower().endswith('.json'):
            mime_type = 'application/json'
        
        # Add Cache-Control header to prevent caching issues with videos
        response = send_from_directory(app.config['RESULT_FOLDER'], safe_filename, mimetype=mime_type)
        if any(ext in filename.lower() for ext in ['.mp4', '.avi', '.webm']):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response

    return app

# This part is typically not needed when using the factory pattern with wsgi.py
# but can be useful for direct `python app.py` execution (though wsgi.py is preferred)
# if __name__ == '__main__':
#     app = create_app()
#     # Use waitress for running locally if needed, matching wsgi.py approach
#     from waitress import serve
#     serve(app, host='0.0.0.0', port=5000)