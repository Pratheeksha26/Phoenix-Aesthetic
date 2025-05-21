from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

load_dotenv("apikey.env")  # Load environment variables from .env

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

# Configure Upload Folder
UPLOAD_FOLDER = "uploads"
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg"}

def allowed_file(filename):
    """Check if the file type is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

def upload_to_imgbb(image_path):
    """Uploads an image to ImgBB and returns the public URL."""
    with open(image_path, "rb") as file:
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY},
            files={"image": file}
        )
    if response.status_code == 200:
        return response.json().get("data", {}).get("url")
    return None

def google_shopping_search(query):
    """Fetch product data from Google Shopping using SerpAPI"""
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_shopping",
        "q": query,
        "google_domain": "google.co.in",
        "gl": "in",
        "hl": "en",
        "api_key": SERPAPI_KEY
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        return {"error": "Failed to fetch data from SerpAPI"}
    return response.json()

def google_image_search(image_path):
    """Upload image to ImgBB, then use Google Lens search on SerpAPI."""
    image_url = upload_to_imgbb(image_path)
    if not image_url:
        return {"error": "Image upload failed"}

    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": SERPAPI_KEY
    }
    response = requests.get("https://serpapi.com/search", params=params)
    if response.status_code != 200:
        return {"error": "Failed to fetch image search results"}
    return response.json()

@app.route("/search/text", methods=["GET"])
def search_by_text():
    """Search for products using a text query"""
    query = request.args.get("query")
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    results = google_shopping_search(query)
    return jsonify(results)

@app.route("/search/image", methods=["POST"])
def search_by_image():
    """Search for similar products using an uploaded image"""
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    # Save the image
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Upload image to ImgBB and perform search
    image_search_results = google_image_search(filepath)
    return jsonify(image_search_results)

if __name__ == "__main__":
    app.run(debug=True)