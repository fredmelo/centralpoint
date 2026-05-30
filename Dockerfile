FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/data

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
