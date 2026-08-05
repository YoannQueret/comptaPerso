# comptaPerso — Multi-user personal finance tracker

*[Lire en français](README_FR.md)*

Self-hosted Flask application: multi-currency accounts, categories/subcategories,
transactions, inter-account transfers (multi-currency), recurring expenses/income
with adjustable monthly validation, and reports (period comparison, month-by-month,
year-by-year). Interface available in French / English.

## Database migrations (Alembic / Flask-Migrate)

The schema is managed through Alembic migrations (`migrations/`), instead of a
plain `db.create_all()`. This lets the tables evolve later (adding a column, etc.)
without losing existing data.

**With Docker**: migrations are applied automatically when the container starts
(`entrypoint.sh` runs `flask db upgrade` before starting gunicorn). Nothing to do
manually for a standard deployment.

**Without Docker (local dev)**, after cloning/modifying the project:

```bash
export FLASK_APP=run.py
flask db upgrade        # applies existing migrations (first run: creates the tables)
```

**When you change a model** (`app/models.py`), generate a new migration and
apply it:

```bash
export FLASK_APP=run.py
flask db migrate -m "description of the change"   # generates migrations/versions/xxx.py
# → review the generated file (Alembic doesn't detect everything: column renames,
#   type changes on SQLite, etc. may need a manual tweak)
flask db upgrade                                    # applies the change
```

With Docker, to generate a migration after changing the models:

```bash
docker compose exec comptaperso flask db migrate -m "description of the change"
docker compose exec comptaperso flask db upgrade
# then copy the generated file into migrations/versions/ on your host machine
# (it's already in the mounted volume if you mount the code in dev; otherwise
# docker cp comptaperso:/app/migrations/versions/xxx.py migrations/versions/)
```

## Quick start (Docker, SQLite)

```bash
docker compose up -d --build
```

Then open http://your-server:5000 and create a user account.

SQLite data persists in the Docker volume `comptaperso_data`
(`/app/data/compta.db` inside the container).

**Remember to change `SECRET_KEY`** in `docker-compose.yml` before going to production.

**Setting environment variables with Docker**: edit the `environment:` list in
`docker-compose.yml` directly — that's what already sets `SECRET_KEY`,
`DB_ENGINE`, `DATA_DIR`. The file has commented-out examples for the SMTP
settings (uncomment and fill in the ones you need); after editing, re-apply
with:

```bash
docker compose up -d
```

(no `--build` needed for an environment-only change).

**Changing the port with Docker**: `PORT` is the one variable that's also read
by Compose itself (for the `ports:` mapping), not just passed into the
container, so it works differently from the others above — set it in the shell
or in a `.env` file next to `docker-compose.yml` (Compose auto-loads that one;
it's unrelated to this project's own `.env.local`):

```bash
echo "PORT=8080" > .env
docker compose up -d
```

## MariaDB variant

```bash
docker compose -f docker-compose.mariadb.yml up -d --build
```

Change the passwords in that file before starting.

## Without Docker (dev / quick test)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

The app starts at http://localhost:5000 (SQLite in `./data/compta.db`), with
Flask's debugger/auto-reload off by default — set `FLASK_DEBUG=true` (see
below) if you want it while developing.

**Setting environment variables without Docker**: `docker-compose.yml` is what
injects them in the Docker path — running `python run.py` directly, there's no
such mechanism, so you set them yourself in the shell. Copy the example file
and load it before starting the app:

```bash
cp .env.local.example .env.local
# edit .env.local with your own values
source .env.local && python run.py
```

`.env.local` is meant to hold your real local secrets — don't commit it.
(There's no `python-dotenv` auto-loading here; `source`ing the file is what
exports the variables into your shell before `run.py` starts.)

## Configuration (environment variables)

- `SECRET_KEY` — Flask session secret, change it in production.
- `DB_ENGINE` — `sqlite` (default) or `mariadb`.
- `DATA_DIR` — SQLite data directory (default `./data`).
- `ALLOW_REGISTRATION` — set to `false` to disable self-service sign-up once your
  users are set up (default: enabled). The very first account ever created on
  an install automatically gets administrator rights, regardless of this
  setting — admins can still invite new users by email from the "Administration"
  menu even when self-service registration is disabled.
- `PORT` — port the app listens on (default `5000`). Used by `python run.py`
  directly, and by the Docker entrypoint (gunicorn) and the `ports:` mapping in
  `docker-compose*.yml`.
- `FLASK_DEBUG` — set to `true` to enable Flask's debugger/auto-reload for local
  development (default: `false`). **Must stay `false` in production** — the
  debugger allows arbitrary code execution if it's ever reachable from outside.
  Only affects `python run.py`; the Docker path always runs gunicorn and never
  enables it, regardless of this setting.
- `SKIP_DB_UPGRADE` — set to `true` to skip the automatic schema check/upgrade at
  startup (useful for the `flask db ...` commands themselves, or troubleshooting).
- `BACKUP_DIR` / `BACKUP_KEEP` — where SQLite backups are written before each
  startup migration, and how many to keep (default: `./data/backups`, 20).
- `ATTACHMENTS_DIR` — where transaction attachments (receipts, images or PDFs,
  max 10 MB) are stored (default: `./data/attachments`).
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` — outgoing mail
  server, used for "forgot password" emails. Leave `SMTP_HOST` empty to disable
  sending (reset requests still succeed with no visible error, but the email is
  only logged server-side, not delivered — fine for local dev).
- `SMTP_USE_TLS` (default `true`) / `SMTP_USE_SSL` (default `false`) — pick one
  depending on your provider (STARTTLS on port 587 vs implicit TLS on port 465).
- `MAIL_FROM` — the "From" address on outgoing email (default
  `no-reply@comptaperso.local`).
- `PASSWORD_RESET_TOKEN_MAX_AGE` — how long a password reset link stays valid,
  in seconds (default 3600 = 1 hour).

## How recurring rules work (the important part)

1. **Recurring** tab → create a rule (label, account, category, approximate
   amount, periodicity, start date).
2. **Monthly budget** tab: every active rule whose next due date falls within
   the displayed month (or is overdue) shows up at the top, editable row by row
   (amount + exact date).
3. Clicking **Validate** creates the real transaction with the adjusted values
   and automatically computes the next due date based on the periodicity.
4. Occurrences that haven't been validated stay visible (marked "overdue") until
   they're processed — nothing is generated automatically in the background.

## Multi-currency transfers

In **Transfers → Add**, pick the source and destination accounts: if the
currencies differ, enter the amount sent and the amount received separately
(to reflect the real exchange rate / fees). If it's the same currency, the
amount received is copied automatically (editable if needed).

## What's intentionally simplified in this v1

- No CSV/OFX bank import (can be added if useful).
- No single "reference currency" conversion (balances/reports stay per
  account/currency; no aggregated multi-currency conversion for now).
- No charts yet (reports are table-based).

## Project structure

```
app/
  config.py           configuration (SQLite / MariaDB via env vars)
  models.py            User, Account, Category, Transaction, RecurringRule
  utils.py              recurring due-date calculations
  translations.py        fr/en dictionary
  routes/                one blueprint per functional domain
  templates/              Jinja2, custom CSS (no CDN dependency)
Dockerfile
docker-compose.yml            SQLite
docker-compose.mariadb.yml    MariaDB
```
