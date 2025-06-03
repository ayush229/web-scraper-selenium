# main.py
from flask import Flask, request, jsonify, make_response
from functools import wraps
# Assuming scraper.py exists in the same directory with scrape_website and crawl_website
from scraper import scrape_website, crawl_website
import logging
import os
from together import Together # Assuming 'together' library is installed
from urllib.parse import urlparse, urljoin
import uuid
import re
import traceback # Import traceback for detailed error logging
import json # Import json at the top
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://agent-ai-production-b4d6.up.railway.app","https://agent-ai-production-b4d6.up.railway.app/agent"], supports_credentials=True, methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"]) # <--- Add this line here!

# --- Configuration ---
AUTH_USERNAME = "ayush1"
AUTH_PASSWORD = "blackbox098"
SCRAPED_DATA_DIR = "scraped_content"
# Ensure the directory exists
os.makedirs(SCRAPED_DATA_DIR, exist_ok=True)

# --- Initialize Clients and Logging ---
try:
    # Initialize Together API client using the API token from environment variable
    # Ensure TOGETHER_API_KEY environment variable is set
    client = Together()
except Exception as e:
    print(f"FATAL: Could not initialize Together client. Ensure TOGETHER_API_KEY environment variable is set. Error: {e}")
    client = None # Set client to None if initialization fails

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Authentication Decorator ---
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == AUTH_USERNAME and auth.password == AUTH_PASSWORD):
            logger.warning("Unauthorized access attempt.")
            return make_response('Unauthorized: Could not verify your access level for that URL.\nYou have to login with proper credentials', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)
    return decorated

# --- Helper Functions ---

def get_stored_content(unique_code):
    """Retrieves content from a stored JSON file."""
    file_path = os.path.join(SCRAPED_DATA_DIR, f"{unique_code}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error for {file_path}: {e}")
            return None
    return None

def save_scraped_content(unique_code, data):
    """Saves scraped content to a JSON file."""
    file_path = os.path.join(SCRAPED_DATA_DIR, f"{unique_code}.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Content for {unique_code} saved successfully to {file_path}")
        return True
    except IOError as e:
        logger.error(f"Error saving content to {file_path}: {e}")
        return False

# --- API Endpoints ---

@app.route('/')
def home():
    return "The web scraping Flask API is running!"

@app.route('/scrape', methods=['POST'])
@requires_auth
def scrape():
    """
    Scrapes a given URL and returns the content.
    Expects JSON input: {"url": "http://example.com", "type": "beautify"}
    """
    data = request.get_json()
    url = data.get('url')
    scrape_type = data.get('type', 'beautify') # Default to 'beautify'

    if not url:
        return jsonify({"status": "error", "error": "URL is required"}), 400

    logger.info(f"Scraping request received for URL: {url}, Type: {scrape_type}")

    try:
        result = scrape_website(url, scrape_type)
        if result["status"] == "success":
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.error(f"Error during scraping {url}: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/crawl', methods=['POST'])
@requires_auth
def crawl():
    """
    Crawls a given base URL and returns content from multiple pages.
    Expects JSON input: {"url": "http://example.com", "type": "beautify", "max_pages": 10}
    """
    data = request.get_json()
    base_url = data.get('url')
    crawl_type = data.get('type', 'beautify') # Default to 'beautify'
    max_pages = data.get('max_pages', 50) # Default to 50 pages

    if not base_url:
        return jsonify({"status": "error", "error": "Base URL is required"}), 400

    logger.info(f"Crawl request received for Base URL: {base_url}, Type: {crawl_type}, Max Pages: {max_pages}")

    try:
        result = crawl_website(base_url, crawl_type, max_pages)
        if result["status"] == "success":
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.error(f"Error during crawling {base_url}: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/store_agent_data', methods=['POST'])
@requires_auth
def store_agent_data():
    """
    Stores agent data (e.g., scraped content) with a unique code.
    Expects JSON input: {"data": {...}}
    """
    data = request.get_json()
    agent_data = data.get('data')

    if not agent_data:
        return jsonify({"status": "error", "error": "No data provided for storage"}), 400

    unique_code = str(uuid.uuid4())
    logger.info(f"Request to store agent data with unique code: {unique_code}")

    if save_scraped_content(unique_code, agent_data):
        return jsonify({"status": "success", "unique_code": unique_code, "message": "Agent data stored successfully"}), 200
    else:
        return jsonify({"status": "error", "error": "Failed to store agent data"}), 500

@app.route('/update_agent_data/<unique_code>', methods=['PUT'])
@requires_auth
def update_agent_data(unique_code):
    """
    Updates existing agent data identified by a unique code.
    Expects JSON input: {"data": {...}}
    """
    data = request.get_json()
    agent_data = data.get('data')

    if not agent_data:
        return jsonify({"status": "error", "error": "No data provided for update"}), 400

    logger.info(f"Request to update agent data for code: {unique_code}")

    # Check if the file exists before attempting to save
    file_path = os.path.join(SCRAPED_DATA_DIR, f"{unique_code}.json")
    if not os.path.exists(file_path):
        logger.warning(f"Attempted to update non-existent file: {unique_code}")
        return jsonify({"status": "error", "error": f"No stored agent data found for unique_code: {unique_code}"}), 404

    if save_scraped_content(unique_code, agent_data):
        return jsonify({"status": "success", "unique_code": unique_code, "message": "Agent data updated successfully"}), 200
    else:
        return jsonify({"status": "error", "error": "Failed to update agent data"}), 500

@app.route('/delete_agent_data/<unique_code>', methods=['DELETE'])
@requires_auth
def delete_agent_data(unique_code):
    """
    Deletes stored agent data identified by a unique code.
    """
    logger.info(f"Request to delete agent data for code: {unique_code}")
    file_path = os.path.join(SCRAPED_DATA_DIR, f"{unique_code}.json")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Agent data file {unique_code}.json deleted successfully.")
            return jsonify({"status": "success", "unique_code": unique_code, "message": "Agent data deleted successfully"}), 200
        else:
            logger.warning(f"Attempted to delete non-existent file: {unique_code}.json")
            return jsonify({"status": "error", "error": f"No agent data found for unique_code: {unique_code}"}), 404
    except OSError as e:
         error_message = f"Error deleting agent data file {unique_code}: {e}\\n{traceback.format_exc()}"
         logger.error(error_message)
         print(error_message) # For immediate console visibility
         return jsonify({"status": "error", "error": f"Could not delete agent data file"}), 500
    except Exception as e:
         error_message = f"Unexpected error during agent deletion {unique_code}: {e}\\n{traceback.format_exc()}"
         logger.error(error_message)
         print(error_message)
         return jsonify({"status": "error", "error": "An unexpected error occurred during deletion"}), 500


@app.route('/get_stored_file/<unique_code>', methods=['GET'])
@requires_auth
def get_stored_file(unique_code):
    """Retrieves the full content of a stored agent file."""
    logger.info(f"Request to get stored file for code: {unique_code}")
    content = get_stored_content(unique_code) # This now gets the full object
    if content:
        return jsonify({"status": "success", "unique_code": unique_code, "content": content}) # Return the full object
    else:
        logger.warning(f"Stored file not found for code: {unique_code}")
        return jsonify({"status": "error", "error": f"Content not found for unique_code: {unique_code}"}), 404


# --- Main Execution ---
if __name__ == '__main__':
    print(f"Starting Flask server on host 0.0.0.0 port 5000")
    print(f"Serving scraped data from: {os.path.abspath(SCRAPED_DATA_DIR)}")
    # Use waitress or gunicorn for production...
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False) # use_reloader=False for gunicorn/production
