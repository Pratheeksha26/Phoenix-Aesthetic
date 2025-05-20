from flask import Flask, request, jsonify
import requests
import base64
from google import generativeai as genai
from flask_cors import CORS
from dotenv import load_dotenv
import os
import re
import json
import uuid


app = Flask(__name__)
CORS(app, supports_credentials=True)

load_dotenv("apikey.env")

# Initialize Google AI Client
genai.configure(api_key=os.getenv("api_key"))

# Store conversation histories for multiple sessions
conversation_histories = {}

@app.route("/start_session", methods=["POST"])
def start_session():
    data = request.json
    session_id = data.get("session_id", None)
    bot_type = data.get("bot_type", "skincare")  # Default to skincare if not specified
    
    if not session_id:
        session_id = f"{bot_type}_{str(uuid.uuid4())}"
    
    # Only create a fresh conversation history if session_id not present
    if session_id not in conversation_histories:
        conversation_histories[session_id] = []
    return jsonify({
        "status": "Session started", 
        "session_id": session_id,
        "bot_type": bot_type
    })

def generate_ai_content(query, conversation_history, image_data=None):
    try:
        # Core system prompt that explicitly prevents assuming previous conversation
        system_prompt = """You are a friendly, knowledgeable skincare assistant. IMPORTANT GUIDELINES:
        - NEVER assume prior conversations unless explicitly present in the provided history
        - NEVER start responses with phrases like "based on our previous conversation" unless there are actual previous messages
        - Treat each interaction as new unless conversation history is provided
        - Do not reference discussions that haven't happened
        - If this is the first message in a conversation, introduce yourself and respond directly to the query
        - Ask clarifying questions when needed
        - Provide detailed, personalized recommendations
        - Use a warm, conversational tone"""
        
        # Check if this is the first message in the conversation
        is_first_message = len(conversation_history) <= 1

        # Detect if the latest user message contains a skin tone selection
        latest_user_message = None
        for msg in reversed(conversation_history):
            if msg['role'] == 'user':
                latest_user_message = msg['content']
                break
        
        skin_tone_context = ""
        if latest_user_message:
            import re
            match = re.search(r"My skin tone is (\w+(?: \w+)*) \((#[0-9A-Fa-f]{6})\)", latest_user_message)
            if match:
                tone_name = match.group(1)
                color_hex = match.group(2)
                skin_tone_context = f" The user has selected a skin tone: {tone_name} ({color_hex}). Please tailor your skincare advice accordingly."

        # Append skin tone context to system prompt if present
        if skin_tone_context:
            system_prompt += skin_tone_context
        
        if image_data:
            model = genai.GenerativeModel('gemini-1.5-pro')
            
            if isinstance(image_data, str) and "," in image_data:
                image_data = image_data.split(",")[1]
            
            try:
                decoded_image = base64.b64decode(image_data)
                
                if is_first_message:
                    image_prompt = f"""This is the first message in our conversation. 
                    The user has shared a skincare image with the query: "{query if query else 'Please analyze this image'}"
                    {skin_tone_context}
                    
                    Analyze this skincare image in detail. Provide:
                    1. Specific observations about the skin
                    2. Personalized recommendations
                    3. Follow-up questions if needed
                    
                    IMPORTANT: Do NOT reference any previous conversation as this is the first interaction."""
                else:
                    image_prompt = f"""Analyze this skincare image in detail. The user asked: "{query}".
                    {skin_tone_context}
                    Provide:
                    1. Specific observations about the skin
                    2. Personalized recommendations
                    3. Follow-up questions if needed"""
                
                image_parts = [{"mime_type": "image/jpeg", "data": decoded_image}]
                
                generation_config = {
                    "max_output_tokens": 4096,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 40
                }
                
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ]
                
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-pro",
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )
                
                chat = model.start_chat(history=[])
                
                # Always send system prompt first
                chat.send_message(system_prompt)
                
                # Only pass actual conversation history if it exists and isn't the first message
                if not is_first_message and len(conversation_history) > 1:
                    formatted_history = []
                    for msg in conversation_history[:-1]:
                        formatted_history.append(f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}")
                    
                    context_message = "Here is the conversation history:\n" + "\n".join(formatted_history)
                    chat.send_message(context_message)
                
                response = chat.send_message([image_prompt, image_parts[0]])
                
            except Exception as img_error:
                print(f"Image processing error: {str(img_error)}")
                return f"I had trouble processing your image. {str(img_error)}"
                
        else:
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            generation_config = {
                "max_output_tokens": 4096,
                "temperature": 0.7,
                "top_p": 0.9,
                "top_k": 40
            }
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]
            
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            chat = model.start_chat(history=[])
            
            # Always send system prompt first
            chat.send_message(system_prompt)
            
            if is_first_message:
                response_prompt = f"""IMPORTANT: This is the FIRST message in the conversation.
                
                User's question: "{query}"
                
                Respond directly to this question. Do NOT reference any previous conversations or context.
                Do NOT start your response with phrases like "Based on our previous conversation" or "Continuing from where we left off".
                
                Provide a helpful, detailed response as if this is the first time you're discussing this topic with the user."""
            else:
                formatted_history = []
                for msg in conversation_history[:-1]:
                    formatted_history.append(f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}")
                
                context_message = "Previous conversation:\n" + "\n".join(formatted_history)
                chat.send_message(context_message)
                
                response_prompt = f"""User's latest question: "{query}"
                
                Please provide a detailed, helpful response considering:
                - The conversation history shared above
                - Best skincare practices
                - Personalized recommendations"""
            
            response = chat.send_message(response_prompt)
            
        return response.text
        
    except Exception as e:
        print(f"Error in generate_ai_content: {str(e)}")
        return f"Error generating AI content: {str(e)}"

@app.route("/chat", methods=["POST"])
def skincare_chatbot():
    data = request.json
    user_query = data.get("message", "")
    has_image = data.get("hasImage", False)
    image_data = data.get("imageData", None) if has_image else None
    session_id = data.get("session_id", None)
    
    # Create a new session ID if none provided
    if not session_id:
        session_id = str(uuid.uuid4())
        conversation_histories[session_id] = []
    
    # Get the history for this session or initialize it
    if session_id not in conversation_histories:
        conversation_histories[session_id] = []
    
    history = conversation_histories[session_id]
    
    # Validate input
    if not user_query and not has_image:
        return jsonify({"error": "No message or image provided"}), 400
    
    # Add the user message to history
    user_message = {"role": "user", "content": user_query}
    history.append(user_message)
    
    # Generate AI response with the current history
    ai_response = generate_ai_content(user_query, history, image_data)
    
    # Add the assistant response to history
    bot_message = {"role": "assistant", "content": ai_response}
    history.append(bot_message)
    
    # Update session history
    conversation_histories[session_id] = history
    
    return jsonify({
        "response": ai_response,
        "history": history,
        "session_id": session_id
    })

@app.route("/clear_chat", methods=["POST"])
def clear_chat():
    try:
        data = request.json
        session_id = data.get("session_id", None)
        
        if not session_id:
            return jsonify({"error": "No session ID provided"}), 400
        
        # Reset the history to empty list
        conversation_histories[session_id] = []
            
        return jsonify({
            "status": "Chat history cleared",
            "session_id": session_id,
            "history": [],
            "new_session": True
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": f"Error clearing chat: {str(e)}",
            "session_id": session_id
        }), 500

@app.route("/history/<session_id>", methods=["GET"])
def get_history(session_id):
    history = conversation_histories.get(session_id, [])
    return jsonify({"history": history})

# Add endpoint to verify if a session has a genuine conversation history
@app.route("/verify_session/<session_id>", methods=["GET"])
def verify_session(session_id):
    history = conversation_histories.get(session_id, [])
    has_history = len(history) > 0
    message_count = len(history)
    
    return jsonify({
        "session_exists": session_id in conversation_histories,
        "has_history": has_history,
        "message_count": message_count
    })

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5003, debug=True)
