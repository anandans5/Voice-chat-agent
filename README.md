# Voice Chat Agent - ABC Automobile Showroom

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
[![Pipeline](https://img.shields.io/badge/Streaming-Voice--to--Voice-brightgreen.svg)]()

An ultra-low latency, real-time voice-to-voice AI telecaller agent tuned for **ABC Automobile Showroom**. Features full end-to-end audio streaming, customizable system prompts, and instant barge-in cancellation.

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
            [ LLM Engine (Groq / OpenAI / DeepSeek) ]
           (System Prompt: system_prompt.txt)
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

- **Automobile Showroom Telecaller Persona**: Pre-configured via `system_prompt.txt` to act as Alex, a professional sales representative helping customers with car inquiries, test drives, and showroom visits.
- **Standalone System Prompt File**: Easily customize AI behavior and sales scripts in `system_prompt.txt` without editing python code.
- **End-to-End Audio Streaming**: Streams audio from browser mic to Deepgram ASR, streams LLM completion tokens to ElevenLabs TTS, and streams speech back to browser for ultra-low latency interaction.
- **Instant Barge-in (Interruption Support)**: If the user speaks while the assistant is talking, in-flight LLM/TTS generation tasks cancel immediately and browser audio playback flushes instantly.
- **Multi-Provider LLM Support**: Compatible with **Groq** (`llama-3.3-70b-versatile`), **OpenAI** (`gpt-4o-mini`), and **DeepSeek** (`deepseek-chat`).
- **Tuned Studio Voice**: Configured with ElevenLabs `eleven_multilingual_v2` model, studio voice parameters, and 30% reduced speaking speed for natural human speech cadence.
- **Monochrome Glassmorphic UI**: Minimalist black-and-white theme featuring responsive wave animations, hotkey support (<kbd>Spacebar</kbd>), and live transcript status tracking.

---

## Project Structure

```
Voice-chat-agent/
├── system_prompt.txt       # Standalone AI Telecaller system prompt configuration
├── .env                    # Environment settings (created from .env.example)
├── .env.example            # Environment template file
├── .gitignore              # Git ignore rules (excludes .env and venv/)
├── requirements.txt        # Python package dependencies
├── config.py               # Settings loader with dynamic system_prompt.txt reading
├── services/
│   ├── __init__.py
│   ├── asr_service.py      # Deepgram WebSocket Live ASR client & KeepAlive loop
│   ├── llm_service.py      # Multi-provider streaming LLM client with memory
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
git clone https://github.com/anandans5/Voice-chat-agent.git
cd Voice-chat-agent

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

# LLM Provider Configuration (OpenAI / Groq / DeepSeek)
OPENAI_MODEL=llama-3.3-70b-versatile
OPENAI_BASE_URL=https://api.groq.com/openai/v1

# Deepgram ASR Settings
DEEPGRAM_MODEL=nova-2

# Server Configuration
HOST=0.0.0.0
PORT=8050
```

---

## Customizing the Telecaller Prompt

Edit `system_prompt.txt` directly to update the AI's script, tone, or showroom details:

```txt
You are Alex, a warm, energetic, and professional customer sales representative from ABC Automobile Showroom.

Your main goal on this phone call is to assist customers with new car inquiries, help them choose the right vehicle (SUV, Sedan, Hatchback, or EV), inform them about ongoing showroom offers, and schedule a test drive or showroom visit.
```

---

## Running the Application

Start the FastAPI application server:

```bash
source venv/bin/activate
python3 main.py
```

Open your browser and navigate to:
**`http://localhost:8050`**

---

## Usage

1. Click the **Microphone Button** (or press <kbd>Spacebar</kbd>) to start the call.
2. Allow microphone access when prompted by your browser.
3. Speak your prompt (e.g., *"Hi, I am looking to buy an SUV under 25 lakhs"*).
4. The AI telecaller will respond in real-time with spoken voice audio.
5. **Barge-in**: Speak at any time while the telecaller is speaking to interrupt and ask a new question.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
