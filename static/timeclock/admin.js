// Admin panel — face capture for employee form
async function initAdminFaceCapture() {
  const captureBtn = document.getElementById('capture-btn');
  const cam = document.getElementById('cam');
  const snapshot = document.getElementById('snapshot');
  const faceStatus = document.getElementById('face-status');
  const descriptorInput = document.getElementById('id_face_descriptor_json');

  if (!captureBtn || !cam) return;

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 320, height: 320 } });
    cam.srcObject = stream;
  } catch (e) {
    if (faceStatus) faceStatus.textContent = 'Câmera não disponível: ' + e.message;
    return;
  }

  // Load face-api models
  await faceapi.nets.ssdMobilenetv1.loadFromUri(FACE_MODEL_URL);
  await faceapi.nets.faceLandmark68Net.loadFromUri(FACE_MODEL_URL);
  await faceapi.nets.faceRecognitionNet.loadFromUri(FACE_MODEL_URL);

  captureBtn.addEventListener('click', async () => {
    captureBtn.disabled = true;
    if (faceStatus) faceStatus.textContent = 'Detectando rosto...';

    const ctx = snapshot.getContext('2d');
    ctx.drawImage(cam, 0, 0, snapshot.width, snapshot.height);

    try {
      const detection = await faceapi
        .detectSingleFace(cam, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.4 }))
        .withFaceLandmarks()
        .withFaceDescriptor();

      if (!detection) {
        if (faceStatus) faceStatus.textContent = 'Nenhum rosto detectado. Tente novamente.';
        captureBtn.disabled = false;
        return;
      }

      const descriptor = Array.from(detection.descriptor);
      if (descriptorInput) descriptorInput.value = JSON.stringify(descriptor);
      if (faceStatus) {
        faceStatus.textContent = '✓ Rosto capturado com sucesso!';
        faceStatus.className = 'text-xs text-green-600';
      }

      // Draw bounding box on snapshot
      const { x, y, width, height } = detection.detection.box;
      const scaleX = snapshot.width / cam.videoWidth;
      const scaleY = snapshot.height / cam.videoHeight;
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 2;
      ctx.strokeRect(x * scaleX, y * scaleY, width * scaleX, height * scaleY);
    } catch (e) {
      if (faceStatus) faceStatus.textContent = 'Erro: ' + e.message;
    }

    captureBtn.disabled = false;
  });
}

document.addEventListener('DOMContentLoaded', initAdminFaceCapture);
