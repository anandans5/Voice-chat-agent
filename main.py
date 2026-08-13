import logging
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from orchestrator import PipelineOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

app = FastAPI(title="Voice-to-Voice Streaming Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

@app.get("/health")
async def health_check():
    has_deepgram = bool(settings.deepgram_api_key and not settings.deepgram_api_key.startswith("your_"))
    has_openai = bool(settings.openai_api_key and not settings.openai_api_key.startswith("your_"))
    has_elevenlabs = bool(settings.elevenlabs_api_key and not settings.elevenlabs_api_key.startswith("your_"))

    return {
        "status": "online",
        "keys_configured": {
            "deepgram": has_deepgram,
            "openai": has_openai,
            "elevenlabs": has_elevenlabs
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New browser client connected to /ws")

    orchestrator = PipelineOrchestrator(websocket)
    try:
        await orchestrator.initialize()
        await orchestrator.send_client_json({"type": "status", "message": "Connected to Voice Agent Backend"})

        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                audio_bytes = message["bytes"]
                await orchestrator.handle_audio_chunk(audio_bytes)

            elif "text" in message and message["text"]:
                try:
                    data = json.loads(message["text"])
                    event_type = data.get("type")

                    if event_type == "barge_in":
                        await orchestrator.trigger_barge_in()
                    elif event_type == "clear_history":
                        orchestrator.llm_service.reset_history()
                        await orchestrator.send_client_json({"type": "status", "message": "Conversation history reset"})
                except Exception as e:
                    logger.warning(f"Failed to parse text message from client: {e}")

            elif message.get("type") == "websocket.disconnect":
                break

    except WebSocketDisconnect:
        logger.info("Browser client disconnected from /ws")
    except Exception as e:
        logger.error(f"Unexpected error in websocket endpoint: {e}")
    finally:
        await orchestrator.cleanup()
        logger.info("Client session cleaned up.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
