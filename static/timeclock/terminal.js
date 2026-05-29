// Live clock
function updateClock() {
  const now = new Date();
  const days = typeof LOCALE_DAYS !== 'undefined' ? LOCALE_DAYS : ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const months = typeof LOCALE_MONTHS !== 'undefined' ? LOCALE_MONTHS : ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const timeStr = now.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const el = document.getElementById('clock');
  if (el) el.textContent = timeStr;
}
setInterval(updateClock, 1000);
updateClock();

// Face recognition terminal
let modelsLoaded = false;
let detecting = false;
let failCount = 0;
const DETECT_INTERVAL_MS = 1500;
const video = document.getElementById('video');
const overlay = document.getElementById('overlay');
const statusBadge = document.getElementById('status-badge');
const resultCard = document.getElementById('result-card');
const resultName = document.getElementById('result-name');
const resultPunch = document.getElementById('result-punch');
const resultTime = document.getElementById('result-time');

async function loadModels() {
  await faceapi.nets.ssdMobilenetv1.loadFromUri(FACE_MODEL_URL);
  await faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL);
  await faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL);
  modelsLoaded = true;
}

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } });
    video.srcObject = stream;
    video.addEventListener('loadedmetadata', () => {
      overlay.width = video.videoWidth;
      overlay.height = video.videoHeight;
    });
  } catch (e) {
    setStatus('Câmera não disponível: ' + e.message, 'red');
  }
}

function setStatus(msg, color) {
  statusBadge.textContent = msg;
  statusBadge.className = 'absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full text-sm font-semibold backdrop-blur ';
  if (color === 'green') statusBadge.className += 'bg-green-600/80 text-white';
  else if (color === 'red') statusBadge.className += 'bg-red-600/80 text-white';
  else statusBadge.className += 'bg-gray-800/80 text-gray-300';
}

function showResult(name, punchLabel, time) {
  resultCard.classList.remove('hidden');
  resultName.textContent = name;
  resultPunch.textContent = punchLabel;
  resultTime.textContent = time;
  setTimeout(() => {
    resultCard.classList.add('hidden');
    detecting = false;
    setStatus(STRINGS.waiting);
  }, 3500);
}

async function detectAndPunch(overrideType) {
  if (!modelsLoaded || detecting) return;
  if (video.readyState < 2) return;

  detecting = true;
  setStatus(STRINGS.detecting, null);

  try {
    const detection = await faceapi
      .detectSingleFace(video, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.5 }))
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (!detection) {
      failCount++;
      setStatus(STRINGS.waiting);
      detecting = false;
      return;
    }

    const descriptor = Array.from(detection.descriptor);
    const body = JSON.stringify({ descriptor, override_type: overrideType || null });

    const resp = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
      body,
    });

    const data = await resp.json();

    if (resp.ok) {
      failCount = 0;
      setStatus(STRINGS.recognized, 'green');
      showResult(data.employee_name, data.punch_type_label, data.punched_at);
      drawBox(detection, 'green');
    } else if (resp.status === 404) {
      failCount++;
      setStatus(STRINGS.not_recognized, 'red');
      drawBox(detection, 'red');
      setTimeout(() => { detecting = false; setStatus(STRINGS.waiting); }, 2000);
    } else if (resp.status === 409) {
      failCount = 0;
      setStatus(data.detail || STRINGS.error, 'red');
      setTimeout(() => { detecting = false; setStatus(STRINGS.waiting); }, 2500);
    } else {
      setStatus(STRINGS.error, 'red');
      detecting = false;
    }
  } catch (e) {
    console.error(e);
    setStatus(STRINGS.error, 'red');
    detecting = false;
  }
}

function drawBox(detection, color) {
  const ctx = overlay.getContext('2d');
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  const { x, y, width, height } = detection.detection.box;
  ctx.strokeStyle = color === 'green' ? '#10b981' : '#ef4444';
  ctx.lineWidth = 3;
  ctx.strokeRect(x, y, width, height);
  setTimeout(() => ctx.clearRect(0, 0, overlay.width, overlay.height), 2000);
}

function manualPunch(type) {
  detectAndPunch(type);
}

async function init() {
  setStatus(STRINGS.waiting);
  await loadModels();
  await startCamera();
  setInterval(() => detectAndPunch(null), DETECT_INTERVAL_MS);
}

init();
