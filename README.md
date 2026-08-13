# Real-Time Voice-to-Voice Conversational Agent

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![Pipeline](https://img.shields.io/badge/Streaming-End--to--End-brightgreen.svg)]()

A ultra-low latency, real-time voice-to-voice AI agent featuring full end-to-end audio streaming and instant barge-in cancellation.

```
[ Browser Mic ] ---> MediaRecorder (150ms chunks)
                           │
                           ▼
                  [ WebSocket /ws ]
                           │
                           ▼
               [ Deepgram Live ASR (nova-2) ]
             (Interim & Final Transcripts + VAD)
                           │
                           ▼
            [ LLM Engine (OpenAI / Groq / DeepSeek) ]
                     (Streaming Tokens)
                           │
                           ▼
                  [ Sentence Chunker ]
                  (Punctuation-buffered)
                           │
                           ▼
               [ ElevenLabs Streaming TTS ]
                 (Multilingual v2 Audio)
                           │
                           ▼
                  [ Web Audio API Player ]
                (Instant Barge-in Flush)
```

---

## Key Features

- **End-to-End Audio Streaming**: Streams audio from browser mic to Deepgram ASR, streams LLM completion tokens to ElevenLabs TTS, and streams audio back to the browser for zero-perceived-latency conversation.
- **Instant Barge-in (Interruption Support)**: If the user starts speaking while the assistant is replying, in-flight LLM/TTS generation tasks cancel immediately and browser audio playback flushes instantly.
- **Multi-Provider LLM Support**: Fully compatible with **OpenAI** (`gpt-4o-mini`), **Groq** (`llama-3.3-70b-versatile`), and **DeepSeek** (`deepseek-chat`).
- **Tuned Studio TTS**: Configured with ElevenLabs `eleven_multilingual_v2` model, studio voice parameters, and 30% reduced speaking speed for crystal-clear, natural human cadence.
- **Resilient Connection & Retry**: Exponential backoff retry logic for API calls, auto-reconnecting WebSocket streams, and KeepAlive ping loops.
- **Monochrome Glassmorphic UI**: Minimalist black-and-white theme featuring responsive wave animations, hotkey support (<kbd>Spacebar</kbd>), and live transcript status tracking.

---

## Directory Structure

```
voice_to_voice_agent/
├── .env                    # Environment settings (created from .env.example)
├── .env.example            # Environment template file
├── requirements.txt        # Python package dependencies
├── config.py               # Application settings loader
├── services/
│   ├── __init__.py
│   ├── asr_service.py      # Deepgram WebSocket Live ASR client & KeepAlive loop
│   ├── llm_service.py      # Multi-provider streaming LLM client with conversation memory
│   └── tts_service.py      # ElevenLabs streaming TTS client with voice tuning
├── orchestrator.py         # Pipeline manager, silence timer, turn lock, barge-in controller
├── main.py                 # FastAPI application, WebSocket /ws endpoint, static server
├── static/
│   ├── index.html          # Single-page monochrome HTML UI
│   ├── app.js              # Web Audio API audio queue player & mic capture
│   └── style.css           # High-contrast black & white styling
└── README.md               # GitHub project documentation
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.11 or higher
- Git

### 2. Clone Repository & Setup Environment
```bash
git clone https://github.com/your-username/voice-to-voice-agent.git
cd voice-to-voice-agent

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate    # On Linux/macOS
# venv\Scripts\activate     # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your API keys in `.env`:

```env
# Required API Keys
DEEPGRAM_API_KEY=your_deepgram_api_key
OPENAI_API_KEY=your_llm_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key

# ElevenLabs Voice Settings
ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
ELEVENLABS_MODEL_ID=eleven_multilingual_v2

# LLM Provider Configuration (Choose OpenAI, Groq, or DeepSeek)
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=

# System Persona
SYSTEM_PROMPT="You are a helpful, concise, and conversational AI voice assistant. Keep your answers brief (1-3 sentences), warm, and engaging, optimized for natural spoken interaction."

# Deepgram ASR Settings
DEEPGRAM_MODEL=nova-2

# Server Configuration
HOST=0.0.0.0
PORT=8050
```

---

## Supported LLM Providers

### 1. OpenAI (Default)
```env
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=
```

### 2. Groq (Free & Fast Llama 3.3)
```env
OPENAI_API_KEY=gsk_...
OPENAI_MODEL=llama-3.3-70b-versatile
OPENAI_BASE_URL=https://api.groq.com/openai/v1
```

### 3. DeepSeek
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com
```

---

## Running the Application

Start the FastAPI application server:

```bash
source venv/bin/activate
python3 main.py
```

Or using Uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8050 --reload
```

Open your browser and navigate to:
**`http://localhost:8050`**

---

## Usage

1. Click the **Microphone Button** (or press <kbd>Spacebar</kbd>) to activate audio input.
2. Grant microphone permissions when prompted by your browser.
3. Speak your prompt into the mic.
4. The system will transcribe your speech, generate an LLM response, and stream studio-quality speech audio back in real-time.
5. **Barge-in**: Speak at any point while the assistant is talking to immediately cancel playback and start a new turn.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
