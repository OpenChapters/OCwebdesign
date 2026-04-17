# OpenChapters Deployment Guide

This guide covers deploying the OpenChapters web platform to a production server.

---

## Table of Contents

1. [Server Requirements](#server-requirements)
2. [Architecture Overview](#architecture-overview)
3. [Initial Server Setup](#initial-server-setup)
4. [Configuration](#configuration)
5. [Building and Starting](#building-and-starting)
6. [Database Initialization](#database-initialization)
7. [Running Tests](#running-tests)
8. [Email Delivery (SMTP)](#email-delivery-smtp)
9. [Cloudflare Turnstile (Bot Protection)](#cloudflare-turnstile-bot-protection)
10. [SSL with Let's Encrypt](#ssl-with-lets-encrypt)
11. [Domain and DNS](#domain-and-dns)
12. [Updating the Application](#updating-the-application)
13. [Database Backups](#database-backups)
14. [Monitoring and Logs](#monitoring-and-logs)
15. [Troubleshooting](#troubleshooting)
16. [Security Checklist](#security-checklist)

---

## Server Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| RAM | 4 GB | 8 GB |
| Disk | 20 GB | 50 GB |
| CPU | 2 cores | 4 cores |
| OS | Linux (Ubuntu 22.04+, Debian 12+) | Ubuntu 24.04 LTS |

The TeX Live installation in the worker image is approximately 5 GB. LaTeX builds are CPU-intensive and can take 1–3 minutes per book.

**Required software:**
- Docker Engine 24+ and Docker Compose v2
- Git (for cloning the repository)

Recommended providers: DigitalOcean (Droplet), Hetzner (Cloud), AWS EC2, or any VPS with Docker support.

## Architecture Overview

```
Internet
   │
   ▼  :80 / :443
┌──────────┐
│  nginx   │  Serves React SPA, proxies /api/ and /admin/ to Django
└────┬─────┘
     │  :8000 (internal)
┌────▼─────┐
│ gunicorn │  Django API (3 workers)
│          │  Static files via whitenoise
└──┬────┬──┘
   │    │
┌──▼──┐ ┌▼──────────┐
│ PG  │ │ RabbitMQ  │
└─────┘ └──┬────────┘
            │
       ┌────▼────┐
       │ Celery  │  TeX Live worker (LaTeX builds)
       │ worker  │
       └─────────┘
```

All services run as Docker containers managed by `docker-compose.prod.yml`.

## Initial Server Setup

### 1. Install Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect
```

### 2. Clone the Repository

```bash
git clone https://github.com/OpenChapters/OCwebdesign.git
cd OCwebdesign
```

### 3. Create a Git Access Token

The application needs a token to sync chapters from the chapter repository. The platform supports both GitHub and GitLab.

**For GitHub (default):**
1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Select scopes: `repo` (read access to public repos is sufficient)
4. Copy the token and set `GITHUB_TOKEN` in `.env.prod`

**Note:** Fine-grained PATs may be blocked by the OpenChapters organization policy if the token lifetime exceeds 366 days. Use a classic PAT for reliable access.

**For GitLab:**
1. Go to your GitLab instance → User Settings → Access Tokens
2. Create a token with `read_repository` scope
3. Set the following in `.env.prod`:
   ```
   GIT_PROVIDER=gitlab
   GIT_TOKEN=glpat-<your_token>
   GIT_BASE_URL=https://gitlab.example.com
   ```

## Configuration

### 1. Create the Production Environment File

```bash
cp .env.prod.example .env.prod
```

### 2. Edit `.env.prod`

```bash
# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Generate a secure database password
openssl rand -hex 24
```

Fill in all values:

```env
# Django
SECRET_KEY=<paste generated secret key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DATABASE_URL=postgres://ocweb:<db_password>@db:5432/ocweb
POSTGRES_DB=ocweb
POSTGRES_USER=ocweb
POSTGRES_PASSWORD=<db_password>

# Celery / RabbitMQ
CELERY_BROKER_URL=amqp://ocweb:<rabbitmq_password>@rabbitmq:5672//
CELERY_RESULT_BACKEND=rpc://
RABBITMQ_DEFAULT_USER=ocweb
RABBITMQ_DEFAULT_PASS=<rabbitmq_password>

# Git provider ("github" or "gitlab")
GIT_PROVIDER=github
GITHUB_TOKEN=ghp_<your_classic_pat>
# For GitLab, use instead:
# GIT_PROVIDER=gitlab
# GIT_TOKEN=glpat-<your_gitlab_token>
# GIT_BASE_URL=https://gitlab.example.com

# Email delivery via SMTP. See "Email Delivery" section for options:
#   Option A — institutional relay (e.g., relay.andrew.cmu.edu, port 25, no auth)
#   Option B — third-party provider (Brevo, Mailgun, SES, etc.)
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
FROM_EMAIL=noreply@yourdomain.com
SITE_URL=https://yourdomain.com
PDF_LINK_EXPIRY_DAYS=7

# Cloudflare Turnstile (bot protection on registration)
TURNSTILE_SITE_KEY=<your_turnstile_site_key>
TURNSTILE_SECRET_KEY=<your_turnstile_secret_key>

# Optional: path to local monorepo clone (for admin thumbnail updates)
# Only needed if the server has a local clone of the OpenChapters repo
OPENCHAPTERS_MONOREPO_PATH=
```

**Important:**

- Use only alphanumeric characters in `POSTGRES_PASSWORD` (avoid `@`, `/`, `#` which break the `DATABASE_URL` parser)
- The password must match in both `DATABASE_URL` and `POSTGRES_PASSWORD`
- Never commit `.env.prod` to version control

### 3. Update nginx Server Name (Optional)

If you want nginx to enforce a specific domain, edit `docker/nginx/nginx.conf`:

```nginx
server_name yourdomain.com www.yourdomain.com;
```

## Building and Starting

```bash
# Build all images (includes frontend compilation)
docker compose -f docker-compose.prod.yml up --build -d
```

This builds three custom images:

- **nginx** — multi-stage: compiles React frontend, bundles into nginx:alpine
- **web** — multi-stage: compiles frontend, installs Django + gunicorn, runs collectstatic
- **worker** — TeX Live base image + Python dependencies + build pipeline scripts

The initial build takes 5–10 minutes due to the TeX Live image (~5 GB).

### Verify Services Are Running

```bash
docker compose -f docker-compose.prod.yml ps
```

All services should show `running`:

```
NAME                     STATUS
ocwebdesign-nginx-1      Up
ocwebdesign-web-1        Up
ocwebdesign-worker-1     Up
ocwebdesign-db-1         Up
ocwebdesign-rabbitmq-1   Up
```

## Database Initialization

Run these commands once after the first deployment:

```bash
# Apply database migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Create an admin user
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Sync the chapter catalog from GitHub
docker compose -f docker-compose.prod.yml exec web python manage.py sync_chapters
```

The chapter catalog is automatically synced nightly at 03:00 UTC via Celery Beat. To enable this, add a beat service to `docker-compose.prod.yml`:

```yaml
  beat:
    build:
      context: .
      dockerfile: docker/web/Dockerfile.prod
    command: celery -A ocweb beat -l info
    env_file: .env.prod
    environment:
      - DJANGO_SETTINGS_MODULE=ocweb.settings.prod
    depends_on:
      - db
      - rabbitmq
    restart: unless-stopped
```

Or run the sync manually as needed:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py sync_chapters
```

## Running Tests

The project includes a test suite (91 tests) built with pytest-django, covering authentication, book management, admin API, build pipeline validation, and signed download tokens.

### Running the Full Suite

```bash
# Development environment
docker compose run --rm web pytest

# Production environment
docker compose -f docker-compose.prod.yml run --rm web pytest
```

### Running with Coverage Report

```bash
docker compose run --rm web pytest --cov=books --cov=catalog --cov=users --cov=admin_api --cov-report=term-missing
```

### Running Specific Test Files

```bash
# Auth tests only
docker compose run --rm web pytest tests/test_auth.py

# Build pipeline validation only
docker compose run --rm web pytest tests/test_build_pipeline.py

# Admin API tests only
docker compose run --rm web pytest tests/test_admin.py
```

### Running by Keyword

```bash
# All tests containing "security" or "permission"
docker compose run --rm web pytest -k "permission or security"

# All tests for build trigger
docker compose run --rm web pytest -k "build_trigger"
```

### Test Coverage Summary

| Module | Tests | What is covered |
|---|---|---|
| Auth | 19 | Registration (with CAPTCHA), login (JWT claims), profile, password change/reset |
| Chapters | 9 | Published filtering, pagination, types, dependencies |
| Books | 20 | CRUD, parts, chapters, reorder, atomic build trigger |
| Build pipeline | 12 | Request serialization, foundational dependency auto-inclusion, input validation |
| Admin | 24 | Permissions, dashboard, user/chapter/build management, settings, audit log |
| Signing | 5 | Token roundtrip, tampering detection, expiry |

### When to Run Tests

- **Before deploying** — run the full suite to catch regressions
- **After updating code** — run tests relevant to the changed area
- **After database migrations** — run the full suite to verify model changes

### Adding New Tests

Tests are in the `tests/` directory:

```
tests/
  conftest.py           Shared fixtures (users, auth clients, books)
  factories.py          Model factories (factory-boy)
  test_auth.py          Authentication and profile tests
  test_books.py         Book CRUD, parts, chapters, build trigger
  test_build_pipeline.py  Build data validation and security
  test_chapters.py      Chapter catalog API tests
  test_admin.py         Admin panel API tests
  test_signing.py       Signed download token tests
```

Follow the existing patterns: use `@pytest.mark.django_db` for database tests, use the fixtures from `conftest.py` (`user`, `auth_client`, `staff_client`, `book`, etc.), and use factories from `factories.py` for creating test data.

## Email Delivery (SMTP)

When a user's book build completes, OpenChapters sends them an email with a signed download link for the PDF. Password reset emails use the same path. OpenChapters talks to **any SMTP server** via Django's built-in SMTP backend, so there are two common options:

- **Option A — Institutional / campus relay** (recommended when available). Many universities run an SMTP relay that accepts mail from allow-listed hosts with no authentication. This is the simplest and most reliable setup: no account to manage, no API keys, no deliverability tuning.
- **Option B — Third-party provider** like [Brevo](https://www.brevo.com/) (300 emails/day free), Mailgun, AWS SES, or SendGrid. Use this if you don't have an institutional relay.

Pick one of the two below.

### Option A: Institutional SMTP Relay

**Prerequisites:** Your deployment host must be added to the relay's allow list. For CMU this means asking CMU Computing Services (or your department's IT group) to add your VM to the `relay.andrew.cmu.edu` access list; other institutions have equivalent processes.

Once the host is allow-listed, update `.env.prod`:

```env
EMAIL_HOST=relay.andrew.cmu.edu
EMAIL_PORT=25
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=False
FROM_EMAIL=noreply@openchapters.materials.cmu.edu
SITE_URL=https://openchapters.materials.cmu.edu
PDF_LINK_EXPIRY_DAYS=7
```

Then restart:

```bash
docker compose -f docker-compose.prod.yml restart web worker
```

**Notes:**

- The relay authorizes you by source IP, so `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` stay blank.
- Port 25 is the convention for internal relays. If your relay requires STARTTLS, use port 587 and set `EMAIL_USE_TLS=True`.
- `FROM_EMAIL` should use a domain your host is authorized to send for. Relays typically reject mail claiming `From:` addresses outside their scope. When in doubt, ask IT which envelope sender they expect.
- No local postfix/MTA is needed — Django opens an SMTP connection to the relay directly. Running postfix just to forward mail to the same relay is unnecessary complexity.

### Option B: Brevo (or other third-party provider)

Use this path if no institutional relay is available.

1. Sign up at https://www.brevo.com/ and complete onboarding (no credit card required).
2. In the Brevo dashboard, click your account name → **SMTP & API** → **SMTP** tab.
3. Note the SMTP server (`smtp-relay.brevo.com`), port (`587`), and login (your account email).
4. Click **Generate a new SMTP key** and copy it — this is your `EMAIL_HOST_PASSWORD`.
5. Authenticate your sending domain under **Senders, Domains & Dedicated IPs → Domains** by adding the DKIM/DMARC DNS records Brevo displays. Without this, mail will likely be marked as spam.

Then update `.env.prod`:

```env
EMAIL_HOST=smtp-relay.brevo.com
EMAIL_PORT=587
EMAIL_HOST_USER=<your_brevo_login_email>
EMAIL_HOST_PASSWORD=<your_brevo_smtp_key>
EMAIL_USE_TLS=True
FROM_EMAIL=noreply@yourdomain.com
SITE_URL=https://yourdomain.com
PDF_LINK_EXPIRY_DAYS=7
```

And restart `web` and `worker`.

For other providers, only the four `EMAIL_*` variables change:

| Provider | `EMAIL_HOST` | Port | `EMAIL_HOST_USER` |
|---|---|---|---|
| Brevo | `smtp-relay.brevo.com` | 587 | account email |
| Mailgun | `smtp.mailgun.org` | 587 | `postmaster@mg.yourdomain.com` |
| SendGrid | `smtp.sendgrid.net` | 587 | `apikey` (literal string) |
| AWS SES | `email-smtp.<region>.amazonaws.com` | 587 | SES SMTP username |
| Gmail | `smtp.gmail.com` | 587 | account email (app password) |

### Variable Reference

| Variable | Description |
|---|---|
| `EMAIL_HOST` | SMTP server hostname. Leave blank to disable email (download links are logged instead). |
| `EMAIL_PORT` | SMTP port (25 for most campus relays; 587 for STARTTLS; 465 for implicit SSL). |
| `EMAIL_HOST_USER` | SMTP login. Blank for IP-allow-listed relays. |
| `EMAIL_HOST_PASSWORD` | SMTP password / API key. Blank for IP-allow-listed relays. |
| `EMAIL_USE_TLS` | `True` for STARTTLS (port 587); `False` for plain port 25 or implicit-SSL port 465. |
| `FROM_EMAIL` | The sender address shown in emails. Must be on a domain the relay/provider allows. |
| `SITE_URL` | The public URL of your site (used to build download links in emails). |
| `PDF_LINK_EXPIRY_DAYS` | How many days the signed download link in the email remains valid (default: 7). |

### How It Works

1. When a build completes, the `deliver_pdf` Celery task runs automatically
2. It generates a **signed, time-limited download URL** using Django's `TimestampSigner`
3. It sends a multipart (HTML + plain-text) email via Django's SMTP backend with:
   - A "Download PDF" button linking to the signed URL
   - A link to the user's Library page
4. The download link works without login — the signed token proves it was issued by the server
5. After `PDF_LINK_EXPIRY_DAYS`, the link stops working; the user can still download from their Library while logged in

### Verifying Email Delivery

After configuring SMTP, trigger a test build and check:

```bash
docker compose -f docker-compose.prod.yml logs worker --tail 20 | grep deliver_pdf
```

You should see: `deliver_pdf: email sent to user@example.com`

If SMTP is not configured, you'll see: `deliver_pdf: EMAIL_HOST not set; would email ...` with the download URL logged for manual testing.

If sending fails (bad credentials, unauthenticated domain, etc.), the task retries up to 3 times with exponential backoff; check worker logs for the SMTP error.

## Cloudflare Turnstile (Bot Protection)

The registration page uses [Cloudflare Turnstile](https://www.cloudflare.com/products/turnstile/) to prevent automated bot signups. In development, test keys are used that always pass. For production, you need real keys.

### 1. Create a Cloudflare Account

1. Sign up at https://dash.cloudflare.com/sign-up (free)
2. You do **not** need to use Cloudflare for DNS or CDN — Turnstile works independently

### 2. Add a Turnstile Widget

1. In the Cloudflare dashboard, go to **Turnstile** (left sidebar)
2. Click **Add Site**
3. Enter your site name and domain (e.g., `yourdomain.com`)
4. Choose widget mode:
   - **Managed** (recommended) — Cloudflare decides whether to show a challenge
   - **Non-interactive** — invisible to most users
   - **Invisible** — fully invisible, no widget shown
5. Copy the **Site Key** and **Secret Key**

### 3. Update `.env.prod`

```env
TURNSTILE_SITE_KEY=0x4AAAAAAAXXXXXXXXXXXXXXXX
TURNSTILE_SECRET_KEY=0x4AAAAAAAXXXXXXXXXXXXXXXX
```

| Variable | Description |
|---|---|
| `TURNSTILE_SITE_KEY` | Public key embedded in the frontend widget. |
| `TURNSTILE_SECRET_KEY` | Secret key used by Django to verify the token with Cloudflare's API. |

### 4. Restart Services

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate web
```

The nginx image also needs rebuilding since the frontend bundles the Turnstile widget code:

```bash
docker compose -f docker-compose.prod.yml up --build -d nginx
```

### How It Works

1. The registration page loads the Turnstile widget from Cloudflare's CDN
2. The widget runs a browser challenge (usually invisible) and produces a token
3. When the user submits the form, the token is sent alongside email + password
4. Django's `RegisterSerializer` verifies the token by calling Cloudflare's `siteverify` API
5. If verification fails, registration is rejected with "CAPTCHA verification failed"

### Development Mode

In development, test keys are used by default:

- Site key: `1x00000000000000000000AA` (always passes)
- Secret key: `1x0000000000000000000000000000000AA` (always passes)

These are [Cloudflare's official test keys](https://developers.cloudflare.com/turnstile/troubleshooting/testing/) and require no Cloudflare account.

## SSL with Let's Encrypt

There are two common approaches. **Option A (Certbot + nginx)** is recommended because it uses the nginx container you already have. **Option B (Caddy)** is an alternative if you prefer automatic certificate management with zero configuration.

### Option A: Certbot + nginx (Recommended)

Certbot obtains a free certificate from Let's Encrypt. You then configure your existing nginx container to terminate TLS.

**Step 1 — Install certbot:**

```bash
sudo apt install certbot
```

**Step 2 — Stop the nginx container** so certbot can bind to port 80:

```bash
docker compose -f docker-compose.prod.yml stop nginx
```

**Step 3 — Obtain a certificate:**

```bash
sudo certbot certonly --standalone -d yourdomain.com
```

Replace `yourdomain.com` with your actual domain. If you also want `www.yourdomain.com`, add `-d www.yourdomain.com`. Certbot will validate domain ownership and store the certificate files under `/etc/letsencrypt/live/yourdomain.com/`.

**Step 4 — Mount the certificates into the nginx container.** Add a `volumes` entry to the `nginx` service in `docker-compose.prod.yml`:

```yaml
  nginx:
    build:
      context: .
      dockerfile: docker/nginx/Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      web:
        condition: service_healthy
    restart: unless-stopped
```

Note: ports should include both 80 (for the HTTP→HTTPS redirect) and 443 (for TLS).

**Step 5 — Update `docker/nginx/nginx.conf`** to redirect HTTP to HTTPS and serve TLS on port 443. Replace the entire file contents with:

```nginx
upstream django {
    server web:8000;
}

# Redirect all HTTP traffic to HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    client_max_body_size 10M;

    # ── Security headers ──────────────────────────────────────────────────────
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-src challenges.cloudflare.com; font-src 'self';" always;

    # ── React SPA ─────────────────────────────────────────────────────────────
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # ── Django (API + admin + static) ─────────────────────────────────────────
    location ~ ^/(api|admin|static)/ {
        proxy_pass http://django;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

Replace both occurrences of `yourdomain.com` with your actual domain. All existing security headers and proxy settings are preserved.

**Step 6 — Enable Django's HTTPS settings.** In `.env.prod`, set:

```env
SECURE_SSL_REDIRECT=True
```

This tells Django to redirect any remaining HTTP requests to HTTPS and to set secure cookie flags.

**Step 7 — Rebuild and start:**

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Verify by visiting `https://yourdomain.com` — you should see a valid certificate and a padlock icon.

**Step 8 — Set up auto-renewal.** Let's Encrypt certificates expire every 90 days. Create a cron job or systemd timer to renew automatically. Certbot needs port 80 free during renewal, so stop and restart nginx around it:

```bash
sudo crontab -e
```

Add this line (runs at 3:00 AM on the 1st and 15th of each month):

```
0 3 1,15 * * certbot renew --pre-hook "docker compose -f /home/youruser/OCwebdesign/docker-compose.prod.yml stop nginx" --post-hook "docker compose -f /home/youruser/OCwebdesign/docker-compose.prod.yml start nginx"
```

Replace `/home/youruser/OCwebdesign` with the actual path to your deployment.

### Option B: Caddy (Alternative)

[Caddy](https://caddyserver.com/) is a reverse proxy that automatically obtains and renews Let's Encrypt certificates with zero configuration. Use this instead of the nginx TLS setup above if you prefer a simpler approach. Caddy runs on the host (outside Docker) and proxies to the nginx container.

**Step 1 — Install Caddy:**

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

**Step 2 — Create `/etc/caddy/Caddyfile`:**

```
yourdomain.com {
    reverse_proxy localhost:8080
}
```

Replace `yourdomain.com` with your actual domain.

**Step 3 — Change the nginx port** in `docker-compose.prod.yml` so Caddy can use 80/443:

```yaml
    ports:
      - "8080:80"
```

Do **not** expose port 443 from nginx — Caddy handles TLS on the host.

**Step 4 — Start Caddy:**

```bash
sudo systemctl enable caddy
sudo systemctl start caddy
```

Caddy automatically obtains a certificate from Let's Encrypt (using the HTTP-01 challenge on port 80) and renews it before expiry. No cron jobs or manual renewal needed.

**Step 5 — Enable Django's HTTPS settings.** In `.env.prod`, set:

```env
SECURE_SSL_REDIRECT=True
```

**Step 6 — Restart:**

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate web
```

Verify at `https://yourdomain.com`.

## Domain and DNS

Point your domain to the server's IP address:

| Type | Name | Value |
|---|---|---|
| A | yourdomain.com | `<server IP>` |
| A | www.yourdomain.com | `<server IP>` |

After DNS propagates (up to 48 hours, usually minutes), update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in `.env.prod` and restart:

```bash
docker compose -f docker-compose.prod.yml restart web
```

## Updating the Application

```bash
cd OCwebdesign

# Pull latest code
git pull origin main

# Rebuild and restart (zero-downtime for the database)
docker compose -f docker-compose.prod.yml up --build -d

# Apply any new migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

## Database Backups

### Manual Backup

```bash
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U ocweb ocweb | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Automated Daily Backup

Create a cron job:

```bash
crontab -e
```

Add:

```
0 2 * * * cd /path/to/OCwebdesign && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U ocweb ocweb | gzip > /path/to/backups/ocweb_$(date +\%Y\%m\%d).sql.gz
```

### Restore from Backup

```bash
gunzip -c backup_20260325.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U ocweb ocweb
```

## Monitoring and Logs

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f nginx

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail 100 worker
```

### Check Service Health

All services have Docker healthchecks configured. Services wait for their dependencies to be healthy before starting (e.g., web waits for db and rabbitmq).

```bash
# Service status (includes health column)
docker compose -f docker-compose.prod.yml ps

# Health check endpoint (returns 200 if healthy, 503 if database is down)
curl http://localhost:8080/api/health/

# Resource usage
docker stats
```

### Failed Build Debugging

Failed builds archive key files (main.log, main.tex, build_request.json) to `media/pdfs/failed_builds/<build-uuid>/` for post-mortem debugging. The last 10 failed builds are kept.

```bash
# List archived failed builds
docker compose -f docker-compose.prod.yml exec web ls -la /app/media/pdfs/failed_builds/

# View a failed build's LaTeX log
docker compose -f docker-compose.prod.yml exec web cat /app/media/pdfs/failed_builds/<uuid>/main.log
```

### Check Build Logs

Build logs are stored in the database. Access them via the Django admin at `https://yourdomain.com/admin/` or via the API:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py shell -c "
from books.models import BuildJob
for job in BuildJob.objects.order_by('-id')[:5]:
    status = 'OK' if not job.error_message else 'FAIL'
    print(f'{status}  {job.book.title}  {job.started_at}')
    if job.error_message:
        print(f'  Error: {job.error_message[:200]}')
"
```

## Troubleshooting

### Container won't start (restart loop)

```bash
# Check logs for the failing service
docker compose -f docker-compose.prod.yml logs web --tail 50
```

Common causes:
- **"Port could not be cast to integer"** — special characters in `POSTGRES_PASSWORD` breaking `DATABASE_URL`. Use only hex characters (`openssl rand -hex 24`).
- **"Worker failed to boot"** — Django settings error. Check environment variables.
- **"password authentication failed"** — database password mismatch. The password is set when the volume is first created. To reset: `docker compose -f docker-compose.prod.yml down -v` (destroys all data), then start fresh.

### Build fails with "arara returned non-zero exit status"

Check the build log in the database for LaTeX errors. Common causes:
- Missing LaTeX packages (shouldn't happen with full TeX Live)
- Undefined commands (e.g. unpublished template chapters with placeholder content)
- Missing figures

### Frontend shows blank page

Open the browser developer console (F12 → Console) to see JavaScript errors. Common causes:
- API returning unexpected format (pagination wrapper vs array)
- Stale JWT token in localStorage (clear it and log in again)

### nginx returns 502 Bad Gateway

The gunicorn process isn't running or hasn't started yet:

```bash
docker compose -f docker-compose.prod.yml logs web --tail 20
```

### Chapter sync fails with 401

The git access token is invalid or expired. Generate a new token and update `GITHUB_TOKEN` (or `GIT_TOKEN` for GitLab) in `.env.prod`, then:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate web
```

## Security Checklist

Before going live, verify:

- [ ] `DEBUG=False` in `.env.prod`
- [ ] `SECRET_KEY` is a unique, random string (not the example value)
- [ ] `POSTGRES_PASSWORD` is strong and random (hex characters only)
- [ ] `RABBITMQ_DEFAULT_PASS` is strong and random
- [ ] `.env.prod` is **not** committed to version control
- [ ] `ALLOWED_HOSTS` lists only your domain(s)
- [ ] `CSRF_TRUSTED_ORIGINS` matches your domain(s) with `https://` prefix
- [ ] `SITE_URL` is set to your production HTTPS URL
- [ ] SSL is configured (HTTPS only)
- [ ] Git access token has minimal required permissions (read-only repo access)
- [ ] SMTP credentials are configured and the sending domain is authenticated (DKIM/SPF)
- [ ] `FROM_EMAIL` matches the authenticated sending domain
- [ ] Cloudflare Turnstile keys are set (not the test keys)
- [ ] Database backups are configured
- [ ] Firewall allows only ports 80, 443, and SSH (22)
- [ ] Docker images are rebuilt from the latest code (`--build` flag)
