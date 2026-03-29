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
7. [SendGrid Email Delivery](#sendgrid-email-delivery)
8. [Cloudflare Turnstile (Bot Protection)](#cloudflare-turnstile-bot-protection)
9. [SSL with Let's Encrypt](#ssl-with-lets-encrypt)
10. [Domain and DNS](#domain-and-dns)
11. [Updating the Application](#updating-the-application)
12. [Database Backups](#database-backups)
13. [Monitoring and Logs](#monitoring-and-logs)
14. [Troubleshooting](#troubleshooting)
15. [Security Checklist](#security-checklist)

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

### 3. Create a GitHub Personal Access Token

The application needs a GitHub token to sync chapters from the OpenChapters organization.

1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Select scopes: `repo` (read access to public repos is sufficient)
4. Copy the token for use in the configuration step

**Note:** Fine-grained PATs may be blocked by the OpenChapters organization policy if the token lifetime exceeds 366 days. Use a classic PAT for reliable access.

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

# GitHub
GITHUB_TOKEN=ghp_<your_classic_pat>

# SendGrid (email delivery of PDF download links)
SENDGRID_API_KEY=SG.<your_sendgrid_api_key>
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
    command: celery -A ocweb beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
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

## SendGrid Email Delivery

When a user's book build completes, OpenChapters sends them an email with a signed download link for the PDF. This requires a [SendGrid](https://sendgrid.com/) account.

### 1. Create a SendGrid Account

1. Sign up at https://signup.sendgrid.com/
2. The free tier allows 100 emails/day, which is sufficient for most deployments.

### 2. Create an API Key

1. In the SendGrid dashboard, go to **Settings → API Keys**
2. Click **Create API Key**
3. Give it a name (e.g., "OpenChapters")
4. Select **Restricted Access** and enable only **Mail Send → Full Access**
5. Copy the key (starts with `SG.`)

### 3. Configure Domain Authentication

For reliable email delivery (avoiding spam folders), configure domain authentication:

1. In SendGrid, go to **Settings → Sender Authentication → Domain Authentication**
2. Follow the wizard to add DNS records (CNAME entries) for your domain
3. This proves to email providers that you're authorized to send from `@yourdomain.com`

Without domain authentication, emails may be rejected or marked as spam by recipients' email providers.

### 4. Update `.env.prod`

```env
SENDGRID_API_KEY=SG.<your_api_key>
FROM_EMAIL=noreply@yourdomain.com
SITE_URL=https://yourdomain.com
PDF_LINK_EXPIRY_DAYS=7
```

| Variable | Description |
|---|---|
| `SENDGRID_API_KEY` | Your SendGrid API key. Leave blank to disable email (download links are logged instead). |
| `FROM_EMAIL` | The sender address shown in emails. Must match your authenticated domain. |
| `SITE_URL` | The public URL of your site (used to build download links in emails). |
| `PDF_LINK_EXPIRY_DAYS` | How many days the signed download link in the email remains valid (default: 7). |

### 5. Restart Services

```bash
docker compose -f docker-compose.prod.yml restart web worker
```

### How It Works

1. When a build completes, the `deliver_pdf` Celery task runs automatically
2. It generates a **signed, time-limited download URL** using Django's `TimestampSigner`
3. It sends an HTML + plain-text email via SendGrid with:
   - A "Download PDF" button linking to the signed URL
   - A link to the user's Library page
4. The download link works without login — the signed token proves it was issued by the server
5. After `PDF_LINK_EXPIRY_DAYS`, the link stops working; the user can still download from their Library while logged in

### Verifying Email Delivery

After configuring SendGrid, trigger a test build and check:

```bash
# Check worker logs for email delivery status
docker compose -f docker-compose.prod.yml logs worker --tail 20 | grep deliver_pdf
```

You should see: `deliver_pdf: email sent to user@example.com (status 202)`

If SendGrid is not configured, you'll see: `deliver_pdf: SENDGRID_API_KEY not set; would email ...` with the download URL logged for manual testing.

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

### Option A: Caddy (Simplest)

[Caddy](https://caddyserver.com/) automatically provisions and renews SSL certificates.

1. Install Caddy on the host (outside Docker)
2. Create `/etc/caddy/Caddyfile`:

```
yourdomain.com {
    reverse_proxy localhost:8080
}
```

3. Change the nginx port in `docker-compose.prod.yml` from `"80:80"` to `"8080:80"` (or any unused port)
4. Start Caddy: `sudo systemctl start caddy`

### Option B: Certbot + nginx

1. Install certbot on the host:
```bash
sudo apt install certbot
```

2. Stop the nginx container temporarily:
```bash
docker compose -f docker-compose.prod.yml stop nginx
```

3. Obtain a certificate:
```bash
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

4. Mount the certificates into the nginx container. Add to `docker-compose.prod.yml` under the `nginx` service:
```yaml
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

5. Update `docker/nginx/nginx.conf` to listen on 443:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # ... rest of the config (location blocks) ...
}
```

6. Add port 443 to `docker-compose.prod.yml`:
```yaml
    ports:
      - "80:80"
      - "443:443"
```

7. Rebuild and start:
```bash
docker compose -f docker-compose.prod.yml up --build -d
```

8. Set up auto-renewal:
```bash
sudo certbot renew --pre-hook "docker compose -f /path/to/docker-compose.prod.yml stop nginx" \
                    --post-hook "docker compose -f /path/to/docker-compose.prod.yml start nginx"
```

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

```bash
# Service status
docker compose -f docker-compose.prod.yml ps

# Resource usage
docker stats
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

The GitHub token is invalid or expired. Generate a new classic PAT and update `GITHUB_TOKEN` in `.env.prod`, then:

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
- [ ] GitHub token has minimal required permissions
- [ ] SendGrid API key is configured and domain authentication is complete
- [ ] `FROM_EMAIL` matches the authenticated SendGrid domain
- [ ] Cloudflare Turnstile keys are set (not the test keys)
- [ ] Database backups are configured
- [ ] Firewall allows only ports 80, 443, and SSH (22)
- [ ] Docker images are rebuilt from the latest code (`--build` flag)
