const video       = document.getElementById('video');
const overlay     = document.getElementById('overlay');
const statusBadge = document.getElementById('status-badge');
const identifyBtn = document.getElementById('identify-btn');

let modelsLoaded = false;
let busy = false;

function setStatus(msg, color) {
  statusBadge.textContent = msg;
  const base = 'absolute bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full text-sm font-semibold backdrop-blur whitespace-nowrap ';
  if      (color === 'green') statusBadge.className = base + 'bg-green-600/80 text-white';
  else if (color === 'red')   statusBadge.className = base + 'bg-red-600/80 text-white';
  else if (color === 'blue')  statusBadge.className = base + 'bg-blue-600/80 text-white';
  else                        statusBadge.className = base + 'bg-gray-800/80 text-gray-300';
}

function drawBox(detection, color) {
  if (!overlay.width || !overlay.height) return;
  const ctx = overlay.getContext('2d');
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  if (!detection) return;
  const { x, y, width, height } = detection.detection.box;
  ctx.strokeStyle = color === 'green' ? '#10b981' : '#ef4444';
  ctx.lineWidth = 3;
  ctx.strokeRect(x, y, width, height);
}

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

async function loadModels() {
  setStatus('Carregando modelos...', 'blue');
  try {
    await faceapi.nets.ssdMobilenetv1.loadFromUri(FACE_MODEL_URL);
    await faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL);
    await faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL);
    modelsLoaded = true;
    identifyBtn.disabled = false;
    setStatus('Pronto — pressione IDENTIFICAR');
  } catch (e) {
    setStatus('Erro ao carregar modelos: ' + e.message, 'red');
  }
}

identifyBtn.addEventListener('click', async () => {
  if (busy || !modelsLoaded) return;
  if (!video.srcObject || video.readyState < 2) {
    setStatus('Câmera não pronta.', 'red');
    return;
  }

  busy = true;
  identifyBtn.disabled = true;
  setStatus('Identificando...', 'blue');

  try {
    const detection = await faceapi
      .detectSingleFace(video, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.4 }))
      .withFaceLandmarks()
      .withFaceDescriptor();

    if (!detection) {
      drawBox(null, null);
      setStatus('Nenhum rosto detectado. Tente novamente.', 'red');
      setTimeout(() => { setStatus('Pronto — pressione IDENTIFICAR'); busy = false; identifyBtn.disabled = false; }, 3000);
      return;
    }

    const descriptor = Array.from(detection.descriptor);
    const resp = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
      body: JSON.stringify({ descriptor }),
    });
    const data = await resp.json();

    if (resp.ok) {
      drawBox(detection, 'green');
      setStatus('Identificado: ' + data.employee_name, 'green');
      setTimeout(() => { window.location.reload(); }, 1200);
    } else if (resp.status === 404) {
      drawBox(detection, 'red');
      setStatus('Não reconhecido. Tente novamente.', 'red');
      setTimeout(() => { setStatus('Pronto — pressione IDENTIFICAR'); busy = false; identifyBtn.disabled = false; }, 3000);
    } else {
      setStatus('Erro ao identificar. Tente novamente.', 'red');
      setTimeout(() => { setStatus('Pronto — pressione IDENTIFICAR'); busy = false; identifyBtn.disabled = false; }, 3000);
    }
  } catch (e) {
    console.error(e);
    setStatus('Erro. Tente novamente.', 'red');
    busy = false;
    identifyBtn.disabled = false;
  }
});

async function init() {
  startCamera();
  await loadModels();
}
init();
