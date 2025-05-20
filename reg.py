from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from datetime import datetime
import os
from dotenv import load_dotenv
import logging
import re


app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv("apikey.env")

# MongoDB Configuration
app.config["MONGO_URI"] = os.getenv("mongo")
mongo = PyMongo(app)

# Explicitly reference the PA database and users collection
try:
    db = mongo.cx["PA"]
    users_collection = db["users"]
    
    # Test database connection
    logger.info("Database connection established")
    logger.info(f"Available databases: {mongo.cx.list_database_names()}")
except Exception as e:
    logger.error(f"Database connection error: {e}")

bcrypt = Bcrypt(app)

# Test Database Connection Route
@app.route('/test_db', methods=['GET'])
def test_db():
    try:
        # Attempt to get server info
        server_info = mongo.cx.server_info()
        logger.info("Database server info retrieved successfully")
        
        # List collections in the database
        collections = db.list_collection_names()
        logger.info(f"Collections in database: {collections}")
        
        return jsonify({
            "message": "Connected to MongoDB Atlas!", 
            "databases": mongo.cx.list_database_names(),
            "collections": collections
        }), 200
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return jsonify({"error": str(e)}), 500

# Register User 
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    logger.info(f"Registration attempt for email: {email}")

    # Check if user already exists
    existing_user = users_collection.find_one({"email": email})
    if existing_user:
        logger.warning(f"Registration attempt for existing email: {email}")
        return jsonify({"message": "Email already registered"}), 400

    try:
        # Hash the password before storing
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Insert user into MongoDB
        result = users_collection.insert_one({
            "full_name": full_name,
            "email": email,
            "password": hashed_password,
            "created_at": datetime.utcnow()
        })

        # Log successful insertion
        logger.info(f"User registered successfully: {result.inserted_id}")

        return jsonify({
            "message": "Registration successful", 
            "user_id": str(result.inserted_id)
        }), 201

    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"message": f"Registration failed: {str(e)}"}), 500

# Login Route
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '')

    logger.info(f"Login attempt for email: {email}")

    try:
        # Find user by email
        user = users_collection.find_one({"email": email})

        if not user:
            logger.warning(f"Login failed: Email not registered - {email}")
            return jsonify({"message": "Email not registered"}), 401

        # Check password
        if bcrypt.check_password_hash(user['password'], password):
            logger.info(f"Successful login for email: {email}")
            return jsonify({"message": "Login successful"}), 200
        else:
            logger.warning(f"Login failed: Incorrect password for email: {email}")
            return jsonify({"message": "Incorrect password"}), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"message": f"Login failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5002, debug=True)
