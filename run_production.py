from waitress import serve
from app import app
import logging

# Configure logging to see access logs
logger = logging.getLogger('waitress')
logger.setLevel(logging.INFO)

if __name__ == "__main__":
    print("🚀 Starting Production Server with Waitress...")
    print("✅ Serving on http://0.0.0.0:8080")
    print("   (Accessible at http://192.168.50.5:8080 and all other server IPs)")
    print("ℹ️  Press Ctrl+C to stop.")
    
    # Threads default is 4, enabling more for concurrency
    serve(app, host='0.0.0.0', port=8080, threads=6)
