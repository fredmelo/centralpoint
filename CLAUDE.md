# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development commands

```bash
# Activate virtualenv
source .venv/bin/activate

# Run dev server
DEBUG=True SECRET_KEY=dev python manage.py runserver

# Run migrations
DEBUG=True SECRET_KEY=dev python manage.py migrate

# Create a new migration after model changes
DEBUG=True SECRET_KEY=dev python manage.py makemigrations

# Compile translations after editing .po files
DEBUG=True SECRET_KEY=dev python manage.py compilemessages

# Collect static files
DEBUG=True SECRET_KEY=dev python manage.py collectstatic --noinput

# Open Django shell
DEBUG=True SECRET_KEY=dev python manage.py shell

# Create superuser
DEBUG=True SECRET_KEY=dev python manage.py createsuperuser
```

There are no automated tests. Verification is done by running the server and exercising the UI manually.

## Environment variables

| Variable | Dev default | Notes |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-not-for-production` (when `DEBUG=True`) | Required in production |
| `DEBUG` | `False` | Set `True` for local dev |
| `ALLOWED_HOSTS` | `*` when DEBUG=True | Comma-separated in production |
| `DATA_DIR` | `BASE_DIR` | Path for `db.sqlite3` and `media/` uploads |
| `TIME_ZONE` | `America/Sao_Paulo` | |
| `FACE_CONFIDENCE_THRESHOLD` | `0.60` | Cosine similarity threshold for face matching |
| `EMAIL_BACKEND` | `console.EmailBackend` | Set SMTP vars for real email |

## Architecture

### Request flow

```
Browser → Django (Gunicorn) → timeclock/views.py
                            → timeclock/balance.py  (hour calculations)
                            → WeasyPrint            (PDF generation)
```

**Kiosk terminal** (`/`): Public page. Camera feed shown continuously. User presses **REGISTRAR PONTO** → browser runs face detection with face-api.js (loads from `cdn.jsdelivr.net`) → sends 128-float descriptor via `POST /api/punch/` → Django runs cosine similarity against stored `Employee.face_descriptor` → creates `PunchRecord`.

**Admin panel** (`/painel/*`): Requires `@staff_member_required`. All routes defined in `timeclock/urls.py`.

### Face recognition

- **Client side**: face-api.js 0.22.2 (CDN). Models load from `cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights` on first use; browser caches them. Descriptors are 128-dimensional float32 vectors.
- **Server side**: `_find_employee()` in `views.py` — numpy cosine similarity across all active employees with a stored descriptor. `Employee.face_descriptor` is a `JSONField` storing a list of 128 floats.
- **Registration**: Admin uploads/captures a photo → browser runs face-api.js and extracts descriptor → sends as hidden form field `face_descriptor_json` → `EmployeeForm.save()` parses and stores it.

### Hour balance

`timeclock/balance.py` contains all balance logic:
- `calculate_day_balance(employee, date)` — returns a dict with punch times, worked timedelta, expected timedelta, and balance. Only approved `AbsenceRecord` entries are credited.
- `get_period_balance(employee, start_date, end_date)` — iterates day by day and aggregates.
- `format_timedelta(td)` — formats a timedelta as `HH:MM` with sign.

The punch sequence is enforced by `next_expected_punch()` in `models.py`: `clock_in → lunch_start → lunch_end → clock_out`. The API auto-detects the next required punch type unless `override_type` is passed.

### i18n

Default language is `pt-br`. Translation strings use Portuguese as msgids. The English `.po` file is at `locale/en/LC_MESSAGES/django.po`. After editing `.po` files, run `compilemessages`. Language switching uses Django's built-in `set_language` view at `/i18n/set_language/`.

`PunchRecord.PUNCH_TYPES` uses `gettext_lazy` so labels are translated at render time.

`timeclock/context_processors.py` injects `LOCALE_DAYS` and `LOCALE_MONTHS` arrays for use in JavaScript.

### Static files / WhiteNoise

Uses `ManifestStaticFilesStorage` (not `CompressedManifestStaticFilesStorage`). The Compressed variant gzip-encodes binary model weight files, corrupting them when TensorFlow.js reads the ArrayBuffer. The Manifest variant adds content hashes for cache-busting without compression.

### Deployment (Easypanel)

- Dockerfile: `python:3.12-slim` + WeasyPrint system deps + Gunicorn
- Persistent volume at `/app/data` — contains `db.sqlite3` and `media/` uploads
- `CMD` runs `migrate` then starts Gunicorn
- After first deploy: create superuser via Easypanel terminal
- HTTPS required — browser blocks camera access on plain HTTP
