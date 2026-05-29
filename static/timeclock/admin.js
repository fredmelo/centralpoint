// Admin panel — face capture for employee form
let adminModelsLoaded = false;
let adminModelsLoading = false;

async function loadAdminModels(statusEl) {
  if (adminModelsLoaded) return true;
  if (adminModelsLoading) return false;

  adminModelsLoading = true;
  if (statusEl) statusEl.textContent = 'Carregando modelos de reconhecimento...';

  try {
    await faceapi.nets.ssdMobilenetv1.loadFromUri(FACE_MODEL_URL);
    await faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL);
    await faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL);
    adminModelsLoaded = true;
    if (statusEl) statusEl.textContent = 'Modelos prontos. Clique em Capturar.';
    return true;
  } catch (e) {
    adminModelsLoading = false;
    if (statusEl) statusEl.textContent = 'Erro ao carregar modelos: ' + e.message;
    console.error('face-api model load error:', e);
    return false;
  }
}

async function initAdminFaceCapture() {
  const captureBtn = document.getElementById('capture-btn');
  const cam = document.getElementById('cam');
  const snapshot = document.getElementById('snapshot');
  const faceStatus = document.getElementById('face-status');
  const descriptorInput = document.getElementById('id_face_descriptor_json');

  if (!captureBtn || !cam) return;

  // Register click listener immediately — before model loading
  captureBtn.addEventListener('click', async () => {
    captureBtn.disabled = true;

    // Draw the current video frame to canvas right away
    const ctx = snapshot.getContext('2d');
    ctx.clearRect(0, 0, snapshot.width, snapshot.height);
    if (cam.readyState >= 2) {
      ctx.drawImage(cam, 0, 0, snapshot.width, snapshot.height);
    } else {
      if (faceStatus) faceStatus.textContent = 'Câmera ainda não pronta. Aguarde.';
      captureBtn.disabled = false;
      return;
    }

    if (faceStatus) faceStatus.textContent = 'Detectando rosto...';

    // Ensure models are loaded
    const ready = await loadAdminModels(faceStatus);
    if (!ready) {
      captureBtn.disabled = false;
      return;
    }

    try {
      const detection = await faceapi
        .detectSingleFace(cam, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.4 }))
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (!detection) {
        if (faceStatus) {
          faceStatus.textContent = 'Nenhum rosto detectado. Tente novamente.';
          faceStatus.className = 'text-xs text-amber-600';
        }
        captureBtn.disabled = false;
        return;
      }

      const descriptor = Array.from(detection.descriptor);
      if (descriptorInput) descriptorInput.value = JSON.stringify(descriptor);

      // Draw bounding box on the already-captured snapshot
      const { x, y, width, height } = detection.detection.box;
      const scaleX = snapshot.width / cam.videoWidth;
      const scaleY = snapshot.height / cam.videoHeight;
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2;
      ctx.strokeRect(x * scaleX, y * scaleY, width * scaleX, height * scaleY);

      if (faceStatus) {
        faceStatus.textContent = '✓ Rosto capturado com sucesso!';
        faceStatus.className = 'text-xs text-green-600';
      }
    } catch (e) {
      if (faceStatus) {
        faceStatus.textContent = 'Erro na detecção: ' + e.message;
        faceStatus.className = 'text-xs text-red-600';
      }
      console.error('face detection error:', e);
    }

    captureBtn.disabled = false;
  });

  // Start camera
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 320, height: 320 },
    });
    cam.srcObject = stream;
    cam.addEventListener('loadedmetadata', () => {
      if (faceStatus) faceStatus.textContent = 'Câmera pronta. Clique em Capturar.';
    });
  } catch (e) {
    if (faceStatus) faceStatus.textContent = 'Câmera não disponível: ' + e.message;
    return;
  }

  // Pre-load models in background (so first click is faster)
  loadAdminModels(null).catch(() => {});
}

document.addEventListener('DOMContentLoaded', initAdminFaceCapture);
