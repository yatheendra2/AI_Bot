from flask import Flask, request, jsonify, send_file
from google import genai
import asyncio
import io
import os

app = Flask(__name__)

# Initialize Gemini client
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Store latest audio response
latest_audio_response = None

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Voice Assistant Backend is running!", "version": "1.0"})

@app.route("/process-audio", methods=["POST"])
def process_audio():
    global latest_audio_response
    
    try:
        audio_data = request.get_data()
        print(f"Received {len(audio_data)} bytes of audio")
        
        # Process with Gemini
        audio_response = asyncio.run(send_to_gemini_live(audio_data))
        latest_audio_response = audio_response
        
        return jsonify({"status": "success", "message": "Audio processed"}), 200
    except Exception as e:
        print(f"Error processing audio: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/get-audio-response", methods=["GET"])
def get_audio_response():
    global latest_audio_response
    
    if latest_audio_response:
        audio_stream = io.BytesIO(latest_audio_response)
        audio_stream.seek(0)
        latest_audio_response = None
        
        return send_file(audio_stream, mimetype="audio/pcm", as_attachment=False)
    else:
        return jsonify({"status": "no_audio", "message": "No audio available"}), 404

async def send_to_gemini_live(audio_data):
    """Send audio to Gemini Live API and get audio response"""
    
    model = "gemini-2.5-flash-native-audio-preview-09-2025"
    
    config = {
        "response_modalities": ["AUDIO"],
        "speech_config": {
            "voice_config": {
                "prebuilt_voice_config": {"voice_name": "Kore"}
            }
        }
    }
    
    audio_chunks = []
    
    async with client.aio.live.connect(model=model, config=config) as session:
        await session.send_realtime_input(
            audio={"data": audio_data, "mime_type": "audio/pcm;rate=16000"}
        )
        
        async for response in session.receive():
            if response.data:
                audio_chunks.append(response.data)
            if response.server_content and response.server_content.turn_complete:
                break
    
    return b"".join(audio_chunks)

if __name__ == "__main__":
    # This runs when using "python3 app.py"
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
