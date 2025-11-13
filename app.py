from flask import Flask, request, jsonify, send_file
from google import genai
import asyncio
import os
import io
import traceback

app = Flask(__name__)

# Initialize Gemini client with better error handling
api_key = "AIzaSyBXW-tcTivYIrAGPS5rMPc-bE70PJaRpqg"

# Don't crash immediately if API key is missing
# Instead, initialize client only when needed
if api_key:
    client = genai.Client(api_key=api_key)
    print("[STARTUP] Gemini API Key: SET ✓")
else:
    client = None
    print("[STARTUP] WARNING: GEMINI_API_KEY not set!")

# Store latest audio response
latest_audio_response = None

@app.route("/", methods=["GET"])
def home():
    api_status = "SET ✓" if api_key else "NOT SET ✗"
    return jsonify({
        "status": "Voice Assistant Backend is LIVE!",
        "project": "ESP32 Voice Assistant with Gemini LLM",
        "api_key_status": api_status,
        "endpoints": {
            "/process-audio": "POST - Send audio from ESP32",
            "/get-audio-response": "GET - Receive audio response"
        }
    })

@app.route("/process-audio", methods=["POST"])
def process_audio():
    global latest_audio_response
    
    # Check if API key is set
    if not client:
        return jsonify({
            "error": "GEMINI_API_KEY not configured",
            "message": "Please set GEMINI_API_KEY environment variable"
        }), 500
    
    try:
        # Get audio data from ESP32
        audio_data = request.get_data()
        print(f"[LOG] Received {len(audio_data)} bytes of audio from ESP32")
        
        if len(audio_data) == 0:
            return jsonify({"error": "No audio data received"}), 400
        
        # Send to Gemini and get audio response
        print("[LOG] Processing with Gemini Live API...")
        audio_response = asyncio.run(send_to_gemini_live(audio_data))
        
        if audio_response:
            latest_audio_response = audio_response
            print(f"[LOG] Received {len(audio_response)} bytes from Gemini")
            return jsonify({
                "status": "success",
                "message": "Audio processed with Gemini",
                "response_size": len(audio_response)
            }), 200
        else:
            return jsonify({"error": "No response from Gemini"}), 500
        
    except Exception as e:
        error_msg = f"Error processing audio: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route("/get-audio-response", methods=["GET"])
def get_audio_response():
    global latest_audio_response
    
    try:
        if latest_audio_response and len(latest_audio_response) > 0:
            print(f"[LOG] Sending {len(latest_audio_response)} bytes of audio to ESP32")
            
            audio_stream = io.BytesIO(latest_audio_response)
            audio_stream.seek(0)
            
            # Clear after sending
            latest_audio_response = None
            
            return send_file(
                audio_stream,
                mimetype="audio/pcm",
                as_attachment=False
            )
        else:
            return jsonify({"status": "no_audio", "message": "Waiting for Gemini response"}), 404
            
    except Exception as e:
        print(f"[ERROR] Error getting audio response: {e}")
        return jsonify({"error": str(e)}), 500

async def send_to_gemini_live(audio_data):
    """Send audio to Gemini Live API and get audio response"""
    
    try:
        model = "gemini-2.5-flash-native-audio-preview-09-2025"
        
        config = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Kore"
                    }
                }
            }
        }
        
        print("[GEMINI] Connecting to Gemini Live API...")
        
        audio_chunks = []
        
        async with client.aio.live.connect(model=model, config=config) as session:
            print("[GEMINI] Connected! Sending audio...")
            
            await session.send_realtime_input(
                audio={
                    "data": audio_data,
                    "mime_type": "audio/pcm;rate=16000"
                }
            )
            print("[GEMINI] Audio sent. Waiting for response...")
            
            async for response in session.receive():
                if response.data:
                    audio_chunks.append(response.data)
                    print(f"[GEMINI] Received audio chunk: {len(response.data)} bytes")
                
                if response.server_content and response.server_content.turn_complete:
                    print("[GEMINI] Response complete!")
                    break
        
        complete_audio = b"".join(audio_chunks)
        print(f"[GEMINI] Total audio response: {len(complete_audio)} bytes")
        
        return complete_audio
        
    except Exception as e:
        error_msg = f"Gemini API Error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"[STARTUP] Starting Voice Assistant Backend...")
    print(f"[STARTUP] Gemini API Key: {'SET ✓' if api_key else 'NOT SET ✗'}")
    print(f"[STARTUP] Running on port {port}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
