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

# Compile translations after editing .po files (.mo files are gitignored — run this on fresh checkouts too)
DEBUG=True SECRET_KEY=dev python manage.py compilemessages

# Collect static files
DEBUG=True SECRET_KEY=dev python manage.py collectstatic --noinput

# Open Django shell
DEBUG=True SECRET_KEY=dev python manage.py shell

# Create superuser
DEBUG=True SECRET_KEY=dev python manage.py createsuperuser
```

There are no automated tests and no linter config. Verification is done by running the server and exercising the UI manually.

Commit messages are in Portuguese with conventional prefixes (`feat:`, `fix:`, `docs:`).

## Environment variables

| Variable | Dev default | Notes |
|---|---|---|
| `SECRET_KEY` | `dev-secret-key-not-for-production` (when `DEBUG=True`) | Required in production |
| `DEBUG` | `False` | Set `True` for local dev |
| `ALLOWED_HOSTS` | `*` when DEBUG=True | Comma-separated in production; also used to build `CSRF_TRUSTED_ORIGINS` (`https://<host>`) |
| `DATA_DIR` | `BASE_DIR` | Path for `db.sqlite3` and `media/` uploads |
| `TIME_ZONE` | `America/Sao_Paulo` | |
| `FACE_CONFIDENCE_THRESHOLD` | `0.60` | Cosine similarity threshold for face matching |
| `EMAIL_BACKEND` | `console.EmailBackend` | For real email also set `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` |
| `PORT` / `WORKERS` | `8000` / `2` | Gunicorn bind port and worker count (Dockerfile) |

## Architecture

Single Django app (`timeclock`) inside project `centralpoint`. SQLite database. Nearly all logic lives in `timeclock/views.py`. Models: `Employee`, `PunchRecord`, `AbsenceRecord` (abono).

### Request flow

```
Browser → Django (Gunicorn) → timeclock/views.py
                            → timeclock/balance.py  (hour calculations)
                            → WeasyPrint            (PDF generation)
```

There are three surfaces:

**Kiosk terminal** (`/`): Public page. Camera feed shown continuously. User presses **REGISTRAR PONTO** → browser runs face detection with face-api.js → sends 128-float descriptor via `POST /api/punch/` → `_find_employee()` matches it → creates `PunchRecord`.

**Meu Ponto** (`/meu-ponto/`): Public employee self-service. The face descriptor goes to `POST /api/identify/`, which matches the employee *without* recording a punch and stores `employee_punch_id` in the session. With that session key set, the employee can view today's punches and their month/30-day balance, and can submit an abono request at `/meu-ponto/abono/`. The request creates an `AbsenceRecord` with `approved_by=None`, and an admin approves it later at `/painel/abonos/<pk>/aprovar/`. `/meu-ponto/sair/` clears the session key.

**Admin panel** (`/painel/*`): Views use `@login_required` + `@staff_member_required`. Login is at `/admin-login/` (custom template), and the stock Django admin is at `/django-admin/`. All app routes are defined in `timeclock/urls.py`.

### Frontend

- No JS build step. Tailwind loads from `cdn.tailwindcss.com` and face-api.js 0.22.2 from `cdn.jsdelivr.net`.
- Page logic is in `static/timeclock/terminal.js` (kiosk), `identify.js` (Meu Ponto) and `admin.js` (employee form face capture). Each template defines globals inline (e.g. `FACE_MODEL_URL`, `CSRF_TOKEN`) before loading its script, so these files depend on template-provided constants.
- `static/face-api/models/` is empty. Model weights load from the jsdelivr CDN URL set in each template.

### Face recognition

- **Client side**: face-api.js extracts 128-dimensional float32 descriptors. Models load from `cdn.jsdelivr.net/gh/justadudewhohacks/face-api.js@0.22.2/weights` on first use, and the browser caches them.
- **Server side**: `_find_employee()` in `views.py` computes numpy cosine similarity against every active employee with a stored descriptor and returns `(employee, score)`, or `(None, best_score)` when the best score is below the threshold. Both `api_punch` and `api_identify` validate that the descriptor is a list of exactly 128 numbers. `Employee.face_descriptor` is a `JSONField` holding a list of 128 floats.
- **Registration**: Admin uploads/captures a photo → browser runs face-api.js and extracts descriptor → sends as hidden form field `face_descriptor_json` → `EmployeeForm.save()` parses and stores it.

### Hour balance

`timeclock/balance.py` contains all balance logic:
- `calculate_day_balance(employee, date)` returns a dict with punch records, `worked`, `expected` (`Employee.daily_hours`) and `balance = worked - expected + approved absence hours`. It returns `None` for days with no `clock_in`, so days with no punches don't count against the employee. When `clock_out` is missing, `worked` and `balance` are `None`.
- `get_period_balance(employee, start_date, end_date)` iterates day by day and returns `rows` plus `total_worked`/`total_expected`/`total_balance`.
- `format_timedelta(td)` formats a timedelta as signed `HH:MM`, or `—` for `None`.

Templates expect pre-formatted `*_fmt` keys (`total_worked_fmt`, `total_expected_fmt`, `total_balance_fmt`, and per-row `worked_fmt`/`balance_fmt`). Each view adds these itself after calling `get_period_balance`. A new view that reuses a template must add every key that template reads, or the value renders blank.

The punch sequence is enforced by `next_expected_punch()` in `models.py`: `clock_in → lunch_start → lunch_end → clock_out`. The API auto-detects the next required punch type unless `override_type` is passed, and returns 409 once all four punches exist.

### Reports / PDF

`report_pdf` and `report_send_email` both render `templates/reports/monthly_report.html` and convert it with WeasyPrint. WeasyPrint is imported **lazily inside the view** on purpose: a module-level import breaks the app wherever the Pango/Cairo system libraries are missing. `weasyprint==62.3` is pinned together with `pydyf==0.10.0`, and the two must be upgraded together.

### i18n

Default language is `pt-br`. Translation strings use Portuguese as msgids. The English `.po` file is at `locale/en/LC_MESSAGES/django.po`. After editing `.po` files, run `compilemessages`. Language switching uses Django's built-in `set_language` view at `/i18n/set_language/`.

`PunchRecord.PUNCH_TYPES` uses `gettext_lazy` so labels are translated at render time.

`timeclock/context_processors.py` injects `LOCALE_DAYS` and `LOCALE_MONTHS` arrays for use in JavaScript.

### Static files / WhiteNoise

Uses `ManifestStaticFilesStorage` (not `CompressedManifestStaticFilesStorage`). The Compressed variant gzip-encodes binary model weight files, corrupting them when TensorFlow.js reads the ArrayBuffer. The Manifest variant adds content hashes for cache-busting without compression.

### Media

Uploads go to `MEDIA_ROOT` (`$DATA_DIR/media`): employee photos in `employees/` and absence attachments in `atestados/`. Django serves them via `django.views.static.serve` in `centralpoint/urls.py` in every environment, production included. WhiteNoise does not serve media.

### Deployment (Easypanel)

- Dockerfile: `python:3.12-slim` + WeasyPrint system deps + Gunicorn. `compilemessages` and `collectstatic` run at build time.
- Persistent volume at `/app/data` — contains `db.sqlite3` and `media/` uploads
- `docker-entrypoint.sh` runs as root: it creates the `media/atestados` and `media/employees` dirs, chowns `$DATA_DIR` (the mounted volume is often root-owned), then drops to `appuser` via `gosu`. `CMD` then runs `migrate` and starts Gunicorn. `DATA_DIR=/app/data` is set in the image.
- After first deploy: create superuser via Easypanel terminal
- HTTPS required — browser blocks camera access on plain HTTP
