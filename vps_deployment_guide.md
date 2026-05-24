# Betopian ERP Microservice — A-Z VPS Deployment Guide

**Domain:** `social-media.betopiagroup.com`
**Project path:** `/root/betopian-erp-microservice`
**Virtualenv:** `/root/betopian-erp-microservice/env`
**OS:** Ubuntu 22.04 | **Web Server:** Nginx | **App Server:** Gunicorn | **DB:** PostgreSQL 16

---

## Table of Contents
1. [Install System Dependencies](#1-install-system-dependencies)
2. [PostgreSQL Setup](#2-postgresql-setup)
3. [Update settings.py](#3-update-settingspy)
4. [Install Gunicorn & Run Django Commands](#4-install-gunicorn--run-django-commands)
5. [Gunicorn systemd Service](#5-gunicorn-systemd-service)
6. [Nginx Configuration](#6-nginx-configuration)
7. [Point Domain DNS to New VPS](#7-point-domain-dns-to-new-vps)
8. [SSL with Certbot](#8-ssl-with-certbot)
9. [Enable HTTPS Security Settings](#9-enable-https-security-settings)
10. [Final Checks](#10-final-checks)
11. [Quick Reference](#11-quick-reference)

---

## 1. Install System Dependencies

```bash
apt update && apt upgrade -y
apt install -y nginx certbot python3-certbot-nginx postgresql postgresql-contrib
```

---

## 2. PostgreSQL Setup

### Create Database & User

```bash
su - postgres
psql
```

Inside psql:

```sql
CREATE DATABASE betopian_db;
CREATE USER betopian_user WITH PASSWORD 'betopian@123';
ALTER ROLE betopian_user SET client_encoding TO 'utf8';
ALTER ROLE betopian_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE betopian_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE betopian_db TO betopian_user;
\q
```

```bash
exit
```

### ⚠️ Fix Schema Permissions (PostgreSQL 15/16)

PostgreSQL 15+ restricts CREATE on the `public` schema by default. Without this fix, `migrate` will fail with `permission denied for schema public`.

```bash
su - postgres
psql -d betopian_db
```

Inside psql:

```sql
GRANT ALL ON SCHEMA public TO betopian_user;
ALTER DATABASE betopian_db OWNER TO betopian_user;
ALTER SCHEMA public OWNER TO betopian_user;
\q
```

```bash
exit
```

---

## 3. Update settings.py

```bash
nano /root/betopian-erp-microservice/config/settings.py
```

Make sure these values are set:

```python
ALLOWED_HOSTS = [
    'social-media.betopiagroup.com',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'betopian_db',
        'USER': 'betopian_user',
        'PASSWORD': 'betopian@123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ⚠️ Leave these commented until SSL is installed (Step 9)
# CSRF_COOKIE_SECURE = True
# SESSION_COOKIE_SECURE = True
# SECURE_SSL_REDIRECT = True
```

---

## 4. Install Gunicorn & Run Django Commands

```bash
cd /root/betopian-erp-microservice
source env/bin/activate

pip install gunicorn psycopg2-binary

python manage.py migrate
python manage.py collectstatic --noinput

deactivate
```

---

## 5. Gunicorn systemd Service

```bash
nano /etc/systemd/system/betopian.service
```

Paste:

```ini
[Unit]
Description=Gunicorn daemon for Betopian ERP Microservice
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/root/betopian-erp-microservice
ExecStart=/root/betopian-erp-microservice/env/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/betopian/betopian.sock \
    --timeout 120 \
    --access-logfile /var/log/betopian/access.log \
    --error-logfile /var/log/betopian/error.log \
    config.wsgi:application
RuntimeDirectory=betopian
RuntimeDirectoryMode=0755

[Install]
WantedBy=multi-user.target
```

```bash
mkdir -p /var/log/betopian

systemctl daemon-reload
systemctl enable betopian
systemctl start betopian

# Verify
systemctl status betopian
```

> ⚠️ If status shows **failed**:
> ```bash
> journalctl -u betopian -n 50 --no-pager
> ```

---

## 6. Nginx Configuration

```bash
mkdir -p /var/www/html
nano /etc/nginx/sites-available/betopian
```

Paste:

```nginx
server {
    listen 80;
    server_name social-media.betopiagroup.com;

    # Must be first — required for SSL certificate issuance
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Static files — admin CSS + app static assets
    location /static/ {
        alias /root/betopian-erp-microservice/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /root/betopian-erp-microservice/media/;
        expires 7d;
    }

    # Proxy all other requests to Gunicorn
    location / {
        include proxy_params;
        proxy_pass http://unix:/run/betopian/betopian.sock;
        proxy_read_timeout 120;
        proxy_connect_timeout 120;
        proxy_send_timeout 120;
    }

    access_log /var/log/nginx/betopian_access.log;
    error_log  /var/log/nginx/betopian_error.log;

    client_max_body_size 20M;
}
```

```bash
# Enable site
ln -s /etc/nginx/sites-available/betopian /etc/nginx/sites-enabled/

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Test and reload
nginx -t && systemctl reload nginx
```

---

## 7. Point Domain DNS to New VPS

> ✅ **This must be done before SSL will work.**

### Check your VPS IP

```bash
curl ifconfig.me
```

### Check what IP the domain currently resolves to

```bash
dig social-media.betopiagroup.com +short
```

If the two IPs are **different**, the domain is still pointing to the old VPS.

### Update DNS A Record

Go to your DNS provider (Cloudflare, GoDaddy, Namecheap, etc.) and update:

```
Type:  A
Name:  social-media
Value: <YOUR NEW VPS IP>
TTL:   300
```

### Wait for propagation then verify

```bash
dig social-media.betopiagroup.com +short
# Must return your new VPS IP before proceeding
```

---

## 8. SSL with Certbot

Once DNS resolves to the correct IP:

```bash
certbot --nginx -d social-media.betopiagroup.com
```

When prompted:
- Enter your email address
- Agree to terms → `A`
- Select **option 2** (redirect HTTP → HTTPS) ✅

```bash
# Test auto-renewal
certbot renew --dry-run
```

Certbot will automatically update your Nginx config to add the HTTPS server block.

---

## 9. Enable HTTPS Security Settings

```bash
nano /root/betopian-erp-microservice/config/settings.py
```

Uncomment these lines:

```python
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
```

Restart Gunicorn:

```bash
systemctl restart betopian
```

---

## 10. Final Checks

```bash
# All services running?
systemctl status betopian
systemctl status nginx
systemctl status postgresql

# Hit the live site
curl -I https://social-media.betopiagroup.com
```

### Admin CSS Check

Visit `https://social-media.betopiagroup.com/admin/` — the login page must be fully styled.

If CSS is missing:

```bash
# Confirm staticfiles exist
ls /root/betopian-erp-microservice/staticfiles/admin/css/

# Test Nginx is serving them
curl -I https://social-media.betopiagroup.com/static/admin/css/base.css
# Must return: HTTP/2 200

# If not, re-run collectstatic
source /root/betopian-erp-microservice/env/bin/activate
python manage.py collectstatic --noinput
deactivate

systemctl reload nginx
```

---

## 11. Quick Reference

| Task | Command |
|------|---------|
| Restart app | `systemctl restart betopian` |
| Reload Nginx | `systemctl reload nginx` |
| App logs (live) | `journalctl -u betopian -f` |
| Gunicorn error log | `tail -f /var/log/betopian/error.log` |
| Nginx error log | `tail -f /var/log/nginx/betopian_error.log` |
| Activate venv | `cd /root/betopian-erp-microservice && source env/bin/activate` |
| Run migrations | `python manage.py migrate` |
| Collect static | `python manage.py collectstatic --noinput` |
| Renew SSL | `certbot renew` |
| Check VPS IP | `curl ifconfig.me` |
| Check DNS | `dig social-media.betopiagroup.com +short` |
| Check DB permissions | `su - postgres && psql -d betopian_db -c "\dn+"` |
| Redis Start Command | `sudo systemctl start redis-server` |
| Verify Redis | `redis-cli ping` |