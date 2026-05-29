// ── Live clock ────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const el = document.getElementById('clock');
  // Fix: use page language so clock matches UI locale (24h PT vs 12h EN)
  const locale = document.documentElement.lang || 'pt-BR';
  if (el) el.textContent = now.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
setInterval(updateClock, 1000);
updateClock();

// ── DOM refs ──────────────────────────────────────────────────────────────────
const video       = document.getElementById('video');
const overlay     = document.getElementById('overlay');
const statusBadge = document.getElementById('status-badge');
const resultCard  = document.getElementById('result-card');
const resultName  = document.getElementById('result-name');
const resultPunch = document.getElementById('result-punch');
const resultTime  = document.getElementById('result-time');
const registerBtn = document.getElementById('register-btn');

// ── State ─────────────────────────────────────────────────────────────────────
let modelsLoaded = false;
let busy         = false;    // true while a punch attempt is in progress

// ── Helpers ───────────────────────────────────────────────────────────────────
function setStatus(msg, color) {
  statusBadge.textContent = msg;
  const base = 'absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full text-sm font-semibold backdrop-blur whitespace-nowrap ';
  if      (color === 'green') statusBadge.className = base + 'bg-green-600/80 text-white';
  else if (color === 'red')   statusBadge.className = base + 'bg-red-600/80 text-white';
  else if (color === 'blue')  statusBadge.className = base + 'bg-blue-600/80 text-white';
  else                        statusBadge.className = base + 'bg-gray-800/80 text-gray-300';
}

function setBusy(state) {
  busy = state;
  registerBtn.disabled = state || !modelsLoaded;
}

function showResult(name, punchLabel, time) {
  resultCard.classList.remove('hidden');
  resultName.textContent  = name;
  resultPunch.textContent = punchLabel;
  resultTime.textContent  = time;
}

function hideResult() {
  resultCard.classList.add('hidden');
}

function drawBox(detection, color) {
  // Fix: guard against 0×0 canvas if loadedmetadata hasn't fired yet
  if (!overlay.width || !overlay.height) return;
  const ctx = overlay.getContext('2d');
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  if (!detection) return;
  const { x, y, width, height } = detection.detection.box;
  ctx.strokeStyle = color === 'green' ? '#10b981' : '#ef4444';
  ctx.lineWidth = 3;
  ctx.strokeRect(x, y, width, height);
}

// ── Camera ────────────────────────────────────────────────────────────────────
async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
    });
    video.srcObject = stream;
    video.addEventListener('loadedmetadata', () => {
      overlay.width  = video.videoWidth;
      overlay.height = video.videoHeight;
    });
  } catch (e) {
    setStatus('Câmera não disponível: ' + e.message, 'red');
  }
}

// ── Models ────────────────────────────────────────────────────────────────────
async function loadModels() {
  setStatus(STRINGS.loading, 'blue');
  registerBtn.disabled = true;
  try {
    await faceapi.nets.ssdMobilenetv1.loadFromUri(FACE_MODEL_URL);
    await faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL);
    await faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL);
    modelsLoaded = true;
    registerBtn.disabled = false;
    setStatus(STRINGS.ready);
  } catch (e) {
    setStatus(STRINGS.model_error + ' ' + e.message, 'red');
    console.error('model load error:', e);
  }
}

// ── Core punch logic ──────────────────────────────────────────────────────────
async function doPunch(overrideType) {
  if (busy || !modelsLoaded) return;
  if (!video.srcObject || video.readyState < 2) {
    setStatus('Câmera não pronta.', 'red');
    return;
  }

  setBusy(true);
  hideResult();
  drawBox(null, null);
  setStatus(STRINGS.detecting, 'blue');

  try {
    const detection = await faceapi
      .detectSingleFace(video, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.4 }))
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (!detection) {
      drawBox(null, null);
      setStatus(STRINGS.no_face, 'red');
      setBusy(false);
      // Auto-clear after 3s so user can try again
      setTimeout(() => setStatus(STRINGS.ready), 3000);
      return;
    }

    const descriptor = Array.from(detection.descriptor);
    const resp = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
      body: JSON.stringify({ descriptor, override_type: overrideType || null }),
    });
    const data = await resp.json();

    if (resp.ok) {
      drawBox(detection, 'green');
      setStatus(STRINGS.recognized, 'green');
      showResult(data.employee_name, data.punch_type_label, data.punched_at);
    } else if (resp.status === 404) {
      drawBox(detection, 'red');
      setStatus(STRINGS.not_recognized, 'red');
    } else if (resp.status === 409) {
      drawBox(detection, 'red');
      setStatus(data.detail || STRINGS.error, 'red');
    } else {
      drawBox(null, null);
      const detail = data.detail || data.error || '';
      setStatus(STRINGS.error + (detail ? ` (${detail})` : ''), 'red');
      console.error('api_punch error:', resp.status, data);
    }
  } catch (e) {
    console.error('punch error:', e);
    setStatus(STRINGS.error, 'red');
  }

  setBusy(false);  // re-enable immediately for error paths with no result card
  // Fix: keep button disabled until result clears to prevent double-punch
  if (resultCard && !resultCard.classList.contains('hidden')) {
    registerBtn.disabled = true;
  }
  setTimeout(() => {
    hideResult();
    drawBox(null, null);
    setStatus(STRINGS.ready);
    setBusy(false);  // final unlock after result display window
  }, 4000);
}

// Exposed for the manual type buttons
function triggerPunch(type) { doPunch(type); }

// ── Wire up button ────────────────────────────────────────────────────────────
registerBtn.addEventListener('click', () => doPunch(null));

// ── Boot ──────────────────────────────────────────────────────────────────────
async function init() {
  startCamera();   // start camera immediately — don't await, runs in parallel
  await loadModels();
}

init();
