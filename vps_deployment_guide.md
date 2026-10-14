# VPS Deployment Guide

| | |
|---|---|
| **Project** | `betopian-erp-microservice` |
| **Path** | `/home/betopia/betopian-erp-microservice/` |
| **VPS** | `betopia@103.161.9.10` |
| **Domain** | `social-media.betopiagroup.com` |
| **Stack** | Django + Daphne + PostgreSQL + Redis + Coturn + Nginx + Docker |

SSH: `ssh betopia@103.161.9.10` → `cd ~/betopian-erp-microservice`

Files to edit on VPS (not in git): `.env`, `secrets/firebase-service-account.json`, `coturn/turnserver.conf`, `/etc/nginx/sites-available/betopian-erp`

---

## 1. Configure app

**`.env`** (production):

```env-example
DEBUG= 
ALLOWED_HOSTS= 
REDIS_URL=
DB_HOST= 
TURN_HOST= 
TURN_SECRET= 
FIREBASE_CREDENTIALS_PATH= 
```

Use `TURN_HOST=103.161.9.10` only during initial IP testing. `DB_HOST` / `REDIS_URL` must use Docker names (`db`, `redis`), not `127.0.0.1`.

**`coturn/turnserver.conf`:**

```conf
external-ip=103.161.9.10
use-auth-secret
static-auth-secret=<same-as-TURN_SECRET>
```

`external-ip` stays the public IP even after domain setup.

---

## 2. Firewall (UFW + cloud panel)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
sudo ufw allow 3478/tcp && sudo ufw allow 3478/udp
sudo ufw allow 5349/tcp && sudo ufw allow 49152:65535/udp
sudo ufw enable
```

Open the same ports in your hosting provider firewall.

---

## 3. Start Docker

```bash
cd ~/betopian-erp-microservice
docker compose build web
docker compose up -d
docker compose ps
docker compose logs -f web
```

`web` runs migrate → collectstatic → Daphne on port `8000`.

---

## 4. DNS

| Type | Name | Value |
|---|---|---|
| A | `social-media` | `103.161.9.10` |
| A | `www.social-media` | `103.161.9.10` |

```bash
dig +short social-media.betopiagroup.com
dig +short www.social-media.betopiagroup.com
```

Both must resolve before Certbot. Missing `www` causes `NXDOMAIN`.

---

## 5. Nginx

```bash
sudo apt update && sudo apt install -y nginx
sudo nano /etc/nginx/sites-available/betopian-erp
```

```nginx
upstream daphne { server 127.0.0.1:8000; }

server {
    listen 80;
    server_name social-media.betopiagroup.com www.social-media.betopiagroup.com 103.161.9.10;
    client_max_body_size 200M;

    location /static/ {
        alias /home/betopia/betopian-erp-microservice/staticfiles/;
    }

    location / {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/betopian-erp /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
curl -I http://social-media.betopiagroup.com/api/schema/
```

---

## 6. SSL

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d social-media.betopiagroup.com -d www.social-media.betopiagroup.com
```

Then update `.env` (`TURN_HOST=social-media.betopiagroup.com`) and restart:

```bash
docker compose up -d web
docker compose restart coturn
sudo systemctl reload nginx
```

---

## 7. Production URLs

| | |
|---|---|
| REST | `https://social-media.betopiagroup.com/api/v1/` |
| Docs | `https://social-media.betopiagroup.com/api/docs/` |
| Admin | `https://social-media.betopiagroup.com/` |
| WebSockets | `wss://social-media.betopiagroup.com/ws/<path>/?token=<jwt>` |
| TURN | `GET /api/v1/turn-credentials/` (auth required) |

---

## 8. Deploy updates

```bash
cd ~/betopian-erp-microservice
git pull
docker compose build web && docker compose up -d web
```

| Changed | Command |
|---|---|
| `.env` | `docker compose up -d web` |
| `coturn/turnserver.conf` | `docker compose restart coturn` |
| Nginx | `sudo nginx -t && sudo systemctl reload nginx` |
| Code only (no deps) | `docker compose restart web` |

---

## 9. Ops

```bash
# Logs
docker compose logs -f web
sudo tail -f /var/log/nginx/error.log

# DB backup
docker compose exec db pg_dump -U postgres betopian > backup_$(date +%Y%m%d).sql

# Migrate
docker compose exec web python manage.py migrate

# Health
curl -I https://social-media.betopiagroup.com/api/schema/
sudo certbot renew
```

---

## Static files & admin CSS

Nginx serves `/static/` from the host `staticfiles/` folder (not from Docker `/app/`).

After deploy or Certbot, the **443** block must keep this location (Certbot usually preserves it):

```nginx
location /static/ {
    alias /home/betopia/betopian-erp-microservice/staticfiles/;
}
```

**Collect static + fix permissions** (Nginx runs as `www-data` and must traverse `/home/betopia/`):

```bash
cd ~/betopian-erp-microservice
docker compose exec web python manage.py collectstatic --noinput
sudo chmod o+x /home/betopia
chmod -R a+rX staticfiles
curl -I https://social-media.betopiagroup.com/static/admin/css/base.css
# Expect: HTTP/2 200
```

`STATIC_URL` in `config/settings.py` must be `/static/` (leading slash).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Admin has no CSS | `collectstatic` + `chmod o+x /home/betopia` + verify `curl -I .../static/admin/css/base.css` |
| Can't save Nginx config | `sudo apt install -y nginx` |
| Certbot `NXDOMAIN` for `www` | Add `www.social-media` A record |
| `502 Bad Gateway` | `docker compose ps` / `docker compose logs web` |
| `DisallowedHost` | Fix `ALLOWED_HOSTS` in `.env`, restart web |
| WebRTC calls fail | Check Coturn ports + `TURN_SECRET` matches coturn config |
