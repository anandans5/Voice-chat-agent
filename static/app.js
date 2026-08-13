let ws = null;
let mediaRecorder = null;
let audioStream = null;
let isMicActive = false;

let audioCtx = null;
let audioQueue = [];
let isPlayingAudio = false;
let currentSourceNode = null;
let scheduledStartTime = 0;

const micBtn = document.getElementById('micBtn');
const micOnIcon = micBtn.querySelector('.mic-on-icon');
const micOffIcon = micBtn.querySelector('.mic-off-icon');
const micHint = document.getElementById('micHint');
const visualizerContainer = document.querySelector('.visualizer-container');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const stateIndicator = document.getElementById('stateIndicator');
const indicatorBadge = document.getElementById('indicatorBadge');
const transcriptBox = document.getElementById('transcriptBox');
const welcomeMsg = document.getElementById('welcomeMsg');
const errorBanner = document.getElementById('errorBanner');
const errorMessage = document.getElementById('errorMessage');

let currentInterimBubble = null;
let currentAssistantBubble = null;

window.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
  initAudioContext();
});

window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
    e.preventDefault();
    toggleMic();
  }
});

function initAudioContext() {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (AudioContextClass) {
    audioCtx = new AudioContextClass();
  } else {
    showError("Web Audio API is not supported in this browser.");
  }
}

function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    updateStatus(true, "Connected");
    hideError();
  };

  ws.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      handleServerEvent(data);
    } catch (e) {}
  };

  ws.onclose = () => {
    updateStatus(false, "Disconnected");
    if (isMicActive) {
      stopMic();
    }
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = () => {
    updateStatus(false, "Connection Error");
  };
}

function updateStatus(connected, text) {
  statusText.textContent = text;
  if (connected) {
    statusDot.className = 'status-dotConnected';
  } else {
    statusDot.className = 'status-dotDisconnected';
  }
}

function setIndicatorState(state, text) {
  indicatorBadge.className = `indicator-badge ${state}`;
  indicatorBadge.textContent = text;

  visualizerContainer.className = 'visualizer-container';
  if (state === 'listening') {
    visualizerContainer.classList.add('listening');
  } else if (state === 'speaking') {
    visualizerContainer.classList.add('speaking');
  }
}

async function toggleMic() {
  if (isMicActive) {
    stopMic();
  } else {
    await startMic();
  }
}

async function startMic() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    showError("Microphone access is not supported by your browser.");
    return;
  }

  if (audioCtx && audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }

  try {
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    mediaRecorder = new MediaRecorder(audioStream, {
      mimeType: getSupportedMimeType()
    });

    mediaRecorder.ondataavailable = async (event) => {
      if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
        const arrayBuffer = await event.data.arrayBuffer();
        ws.send(arrayBuffer);
      }
    };

    mediaRecorder.start(150);
    isMicActive = true;

    micBtn.classList.add('active');
    micOnIcon.classList.add('hidden');
    micOffIcon.classList.remove('hidden');
    micHint.textContent = "Click or press Space to Stop";
    setIndicatorState('listening', 'Listening');

  } catch (err) {
    showError(`Microphone access error: ${err.message}. Please allow mic permissions.`);
  }
}

function getSupportedMimeType() {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/wav'
  ];
  for (const t of types) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return '';
}

function stopMic() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  if (audioStream) {
    audioStream.getTracks().forEach(track => track.stop());
    audioStream = null;
  }
  isMicActive = false;

  micBtn.classList.remove('active', 'speaking');
  micOnIcon.classList.remove('hidden');
  micOffIcon.classList.add('hidden');
  micHint.textContent = "Click or press Space to Start";
  setIndicatorState('idle', 'Idle');
}

function handleServerEvent(data) {
  const { type } = data;

  if (welcomeMsg) {
    welcomeMsg.style.display = 'none';
  }

  switch (type) {
    case 'user_interim':
      renderUserInterim(data.text);
      if (isPlayingAudio && data.text && data.text.trim().length >= 2) {
        handleBargeIn();
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "barge_in" }));
        }
      }
      break;

    case 'user_final':
      renderUserFinal(data.text);
      setIndicatorState('thinking', 'Thinking');
      break;

    case 'assistant_start':
      prepareAssistantTurn();
      break;

    case 'assistant_token':
      appendAssistantToken(data.text);
      break;

    case 'assistant_audio':
      enqueueAudioChunk(data.audio);
      break;

    case 'assistant_end':
      break;

    case 'barge_in':
      handleBargeIn();
      break;

    case 'assistant_interrupted':
      markAssistantInterrupted();
      break;

    case 'error':
      showError(data.message);
      setIndicatorState('idle', 'Error');
      break;

    case 'status':
      break;
  }
}

function renderUserInterim(text) {
  if (!currentInterimBubble) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user';
    msgDiv.innerHTML = `
      <span class="message-label">You</span>
      <div class="message-bubble interim">${escapeHtml(text)}</div>
    `;
    transcriptBox.appendChild(msgDiv);
    currentInterimBubble = msgDiv.querySelector('.message-bubble');
  } else {
    currentInterimBubble.textContent = text;
  }
  scrollToBottom();
}

function renderUserFinal(text) {
  if (currentInterimBubble) {
    currentInterimBubble.className = 'message-bubble';
    currentInterimBubble.textContent = text;
    currentInterimBubble = null;
  } else {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user';
    msgDiv.innerHTML = `
      <span class="message-label">You</span>
      <div class="message-bubble">${escapeHtml(text)}</div>
    `;
    transcriptBox.appendChild(msgDiv);
  }
  scrollToBottom();
}

function prepareAssistantTurn() {
  const msgDiv = document.createElement('div');
  msgDiv.className = 'message assistant';
  msgDiv.innerHTML = `
    <span class="message-label">Assistant</span>
    <div class="message-bubble"></div>
  `;
  transcriptBox.appendChild(msgDiv);
  currentAssistantBubble = msgDiv.querySelector('.message-bubble');
  scrollToBottom();
}

function appendAssistantToken(token) {
  if (!currentAssistantBubble) {
    prepareAssistantTurn();
  }
  currentAssistantBubble.textContent += token;
  scrollToBottom();
}

function markAssistantInterrupted() {
  if (currentAssistantBubble) {
    const interruptedSpan = document.createElement('div');
    interruptedSpan.className = 'interrupted-tag';
    interruptedSpan.textContent = '⚡ [Interrupted by user]';
    currentAssistantBubble.appendChild(interruptedSpan);
  }
}

async function enqueueAudioChunk(base64Audio) {
  if (!audioCtx) return;

  try {
    const binaryStr = atob(base64Audio);
    const len = binaryStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }

    const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);
    audioQueue.push(audioBuffer);

    if (!isPlayingAudio) {
      playAudioQueue();
    }
  } catch (e) {}
}

function playAudioQueue() {
  if (audioQueue.length === 0) {
    isPlayingAudio = false;
    currentSourceNode = null;
    if (isMicActive) {
      setIndicatorState('listening', 'Listening');
      micBtn.classList.remove('speaking');
    } else {
      setIndicatorState('idle', 'Idle');
    }
    return;
  }

  isPlayingAudio = true;
  setIndicatorState('speaking', 'Assistant Speaking');
  micBtn.classList.add('speaking');

  const buffer = audioQueue.shift();
  currentSourceNode = audioCtx.createBufferSource();
  currentSourceNode.buffer = buffer;
  currentSourceNode.connect(audioCtx.destination);

  currentSourceNode.onended = () => {
    playAudioQueue();
  };

  currentSourceNode.start(0);
}

function handleBargeIn() {
  if (currentSourceNode) {
    try {
      currentSourceNode.onended = null;
      currentSourceNode.stop();
    } catch (e) {}
    currentSourceNode = null;
  }
  audioQueue = [];
  isPlayingAudio = false;
  markAssistantInterrupted();
  micBtn.classList.remove('speaking');

  if (isMicActive) {
    setIndicatorState('listening', 'Listening');
  } else {
    setIndicatorState('idle', 'Idle');
  }
}

function clearConversation() {
  transcriptBox.innerHTML = '';
  if (welcomeMsg) {
    welcomeMsg.style.display = 'block';
    transcriptBox.appendChild(welcomeMsg);
  }
  currentInterimBubble = null;
  currentAssistantBubble = null;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "clear_history" }));
  }
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.classList.remove('hidden');
}

function hideError() {
  errorBanner.classList.add('hidden');
}

function scrollToBottom() {
  transcriptBox.scrollTop = transcriptBox.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
