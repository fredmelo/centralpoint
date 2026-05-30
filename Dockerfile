FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/data static/face-api/models

# Download face-api.js + model weights for offline use on the tablet
# --fail: exit non-zero on HTTP errors (prevents saving HTML error pages as model files)
# --retry 3: retry on transient network failures
# --retry-delay 2: wait 2s between retries
RUN curl --fail --retry 3 --retry-delay 2 -L \
        "https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js" \
        -o static/face-api/face-api.min.js && \
    WEIGHTS_BASE="https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights" && \
    for f in ssd_mobilenetv1_model-weights_manifest.json \
              ssd_mobilenetv1_model-shard1 \
              face_landmark_68_model-weights_manifest.json \
              face_landmark_68_model-shard1 \
              face_recognition_model-weights_manifest.json \
              face_recognition_model-shard1 \
              face_recognition_model-shard2; do \
        echo "Downloading $f..." && \
        curl --fail --retry 3 --retry-delay 2 -L \
             "$WEIGHTS_BASE/$f" -o "static/face-api/models/$f" && \
        echo "  OK: $(wc -c < static/face-api/models/$f) bytes"; \
    done

# Update templates to use local models in production
RUN sed -i 's|https://cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights|/static/face-api/models|g' \
    templates/timeclock/punch_terminal.html \
    templates/timeclock/admin/employee_form.html

ENV SECRET_KEY=build-placeholder
RUN python manage.py compilemessages
RUN python manage.py collectstatic --noinput

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV WORKERS=2

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && gunicorn centralpoint.wsgi:application --bind 0.0.0.0:$PORT --workers $WORKERS"]
