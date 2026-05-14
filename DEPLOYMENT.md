# Deployment Guide

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│  Cloudflare Pages   │ ◀─────▶ │  FastAPI Backend     │
│  (React Frontend)   │  CORS   │  (Docker / VPS)      │
│  *.pages.dev        │         │  *.onrender.com      │
└─────────────────────┘         └──────────────────────┘
```

- **Frontend**: Deployed to Cloudflare Pages (static site, global CDN)
- **Backend**: Deployed separately (Render, Railway, Fly.io, AWS, VPS)

---

## Frontend → Cloudflare Pages

### Step 1: Dashboard Settings

In your Cloudflare dashboard:

1. Go to **Workers & Pages** → **Create application** → **Pages** → **Connect to Git**
2. Select your GitHub repo: `abhi-anand-07/csv-mapping-uniblox`
3. Configure build settings:

| Setting | Value |
|---------|-------|
| **Production branch** | `main` |
| **Root directory** | `frontend` |
| **Build command** | `npm install && npm run build` |
| **Build output directory** | `dist` |

4. Add environment variable:

| Variable | Value (example) |
|----------|-----------------|
| `NODE_VERSION` | `20` |

### Step 2: SPA Routing

The `_routes.json` file in `frontend/public/` ensures client-side routing works:
- All paths serve `index.html`
- Static assets (JS, CSS, images) are excluded

### Step 3: API URL

After deploying the backend (see below), update the frontend's API URL:

1. In Cloudflare Pages dashboard → **Settings** → **Environment variables**
2. Add:

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://your-backend-url.com` |

**Do NOT include a trailing slash.**

Example:
```
VITE_API_BASE_URL=https://ai-mapping-api.onrender.com
```

3. Redeploy the frontend (Cloudflare Pages auto-deploys on new commits)

---

## Backend → Render / Railway / Fly.io / VPS

### Option A: Render (Easiest)

1. Create account at [render.com](https://render.com)
2. **New Web Service** → Connect your GitHub repo
3. Configure:

| Setting | Value |
|---------|-------|
| **Root directory** | `backend` |
| **Build command** | `pip install -r requirements.txt` |
| **Start command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

4. Add environment variables in Render dashboard:

| Variable | Value |
|----------|-------|
| `GEMINI_API_KEY` | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `ALLOWED_ORIGINS` | Your Cloudflare Pages URL + any preview URLs |

Example `ALLOWED_ORIGINS`:
```
https://csv-mapping.pages.dev,https://*.csv-mapping.pages.dev
```

### Option B: Docker (Any Platform)

```bash
cd backend
docker build -t ai-mapping-api .
docker run -p 8000:8000 \
  -e GEMINI_API_KEY=xxx \
  -e ALLOWED_ORIGINS=https://your-frontend.pages.dev \
  ai-mapping-api
```

### Option C: Self-Hosted (VPS / EC2)

```bash
# On your server
git clone git@github.com:abhi-anand-07/csv-mapping-uniblox.git
cd csv-mapping-uniblox/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your values

# Run with systemd or supervisor, or use:
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Connecting Frontend ↔ Backend

The frontend uses `VITE_API_BASE_URL` to know where the backend lives:

```typescript
// frontend/src/api.ts
const baseURL = import.meta.env.VITE_API_BASE_URL || '';
```

### CORS

The backend's CORS middleware reads `ALLOWED_ORIGINS` from environment:

```python
# backend/app/config.py
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "...").split(",")
```

**You MUST add your Cloudflare Pages domain to `ALLOWED_ORIGINS`** or API requests will be blocked by the browser.

---

## Preview Deployments

Cloudflare Pages creates a preview URL for every pull request. To allow preview URLs to hit your backend:

1. In Render (or your backend host), set a wildcard CORS origin:
   ```
   ALLOWED_ORIGINS=https://csv-mapping.pages.dev,https://*.csv-mapping.pages.dev
   ```

2. Or use a less restrictive pattern for development:
   ```
   ALLOWED_ORIGINS=*
   ```
   ⚠️ **Not recommended for production.**

---

## Troubleshooting

### "CORS error" in browser console
→ Add your Cloudflare Pages URL to `ALLOWED_ORIGINS` on the backend.

### "404 on page refresh"
→ `_routes.json` is missing from `frontend/public/` or not in `dist/`.

### "API calls fail in production but work locally"
→ `VITE_API_BASE_URL` is not set in Cloudflare Pages environment variables.

### "Build fails on Cloudflare Pages"
→ Make sure **Root directory** is set to `frontend` and build command is `npm install && npm run build`.

---

## Recommended Production Setup

| Service | Purpose | Cost |
|---------|---------|------|
| Cloudflare Pages | Frontend hosting | **Free** |
| Render / Railway | Backend hosting | **Free tier** |
| Total | | **$0/month** |

---

## Cloudflare Migration Note (2026)

Cloudflare is merging Pages into Workers. If you want to future-proof:

1. Install Wrangler: `npm install -g wrangler`
2. Add `wrangler.toml` to `frontend/`
3. Deploy with: `wrangler pages deploy frontend/dist`

The current setup works on both Pages and Workers since we use static asset hosting.
