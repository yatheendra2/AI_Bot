from flask import Flask, request, jsonify, send_file
from google import genai
import asyncio
import os
import io
import traceback

app = Flask(__name__)

# Initialize Gemini client
api_key = "AIzaSyBXW-tcTivYIrAGPS5rMPc-bE70PJaRpqg"

if api_key:
    client = genai.Client(api_key=api_key)
    print("[STARTUP] Gemini API Key: SET ✓")
else:
    client = None
    print("[STARTUP] WARNING: GEMINI_API_KEY not set!")

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
    
    if not client:
        return jsonify({
            "error": "GEMINI_API_KEY not configured"
        }), 500
    
    try:
        audio_data = request.get_data()
        print(f"[LOG] Received {len(audio_data)} bytes")
        
        if len(audio_data) == 0:
            return jsonify({"error": "No audio data"}), 400
        
        print("[LOG] Processing with Gemini...")
        audio_response = asyncio.run(send_to_gemini_live(audio_data))
        
        if audio_response:
            latest_audio_response = audio_response
            print(f"[LOG] Got {len(audio_response)} bytes from Gemini")
            return jsonify({
                "status": "success",
                "response_size": len(audio_response)
            }), 200
        else:
            return jsonify({"error": "No response from Gemini"}), 500
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return jsonify({"error": error_msg}), 500

@app.route("/get-audio-response", methods=["GET"])
def get_audio_response():
    global latest_audio_response
    
    try:
        if latest_audio_response and len(latest_audio_response) > 0:
            print(f"[LOG] Sending {len(latest_audio_response)} bytes to ESP32")
            
            audio_stream = io.BytesIO(latest_audio_response)
            audio_stream.seek(0)
            latest_audio_response = None
            
            return send_file(
                audio_stream,
                mimetype="audio/pcm",
                as_attachment=False
            )
        else:
            return jsonify({"status": "no_audio"}), 404
            
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"error": str(e)}), 500

async def send_to_gemini_live(audio_data):
    try:
        model = "gemini-2.5-flash-native-audio-preview-09-2025"
        
        config = {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": "Kore"}
                }
            }
        }
        
        print("[GEMINI] Connecting...")
        audio_chunks = []
        
        async with client.aio.live.connect(model=model, config=config) as session:
            print("[GEMINI] Sending audio...")
            
            await session.send_realtime_input(
                audio={
                    "data": audio_data,
                    "mime_type": "audio/pcm;rate=16000"
                }
            )
            
            async for response in session.receive():
                if response.data:
                    audio_chunks.append(response.data)
                
                if response.server_content and response.server_content.turn_complete:
                    break
        
        complete_audio = b"".join(audio_chunks)
        print(f"[GEMINI] Response: {len(complete_audio)} bytes")
        
        return complete_audio
        
    except Exception as e:
        print(f"[ERROR] Gemini: {e}")
        raise

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"[STARTUP] Starting on port {port}...")
    app.run(host="0.0.0.0", port=port, debug=False)
