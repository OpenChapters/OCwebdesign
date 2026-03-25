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
7. [SSL with Let's Encrypt](#ssl-with-lets-encrypt)
8. [Domain and DNS](#domain-and-dns)
9. [Updating the Application](#updating-the-application)
10. [Database Backups](#database-backups)
11. [Monitoring and Logs](#monitoring-and-logs)
12. [Troubleshooting](#troubleshooting)
13. [Security Checklist](#security-checklist)

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
┌──▼──┐ ┌▼──────┐
│ PG  │ │ Redis │
└─────┘ └──┬────┘
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

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# GitHub
GITHUB_TOKEN=ghp_<your_classic_pat>

# SendGrid (optional, for email delivery)
SENDGRID_API_KEY=
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
NAME                  STATUS
ocwebdesign-nginx-1   Up
ocwebdesign-web-1     Up
ocwebdesign-worker-1  Up
ocwebdesign-db-1      Up
ocwebdesign-redis-1   Up
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
      - redis
    restart: unless-stopped
```

Or run the sync manually as needed:

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py sync_chapters
```

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
- [ ] `POSTGRES_PASSWORD` is strong and random
- [ ] `.env.prod` is **not** committed to version control
- [ ] `ALLOWED_HOSTS` lists only your domain(s)
- [ ] `CSRF_TRUSTED_ORIGINS` matches your domain(s) with `https://` prefix
- [ ] SSL is configured (HTTPS only)
- [ ] GitHub token has minimal required permissions
- [ ] Database backups are configured
- [ ] Firewall allows only ports 80, 443, and SSH (22)
- [ ] Docker images are rebuilt from the latest code (`--build` flag)
