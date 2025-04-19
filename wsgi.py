# filepath: wsgi.py
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Example using Waitress for local testing mirroring WSGI entry
    # Run this with `python wsgi.py`
    from waitress import serve
    print("Starting server with Waitress on http://0.0.0.0:5000")
    serve(app, host='0.0.0.0', port=5000) 