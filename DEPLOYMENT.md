# ArchScale Deployment Guide

This guide walks through deploying the complete **ArchScale** full-stack system:
- **Backend**: FastAPI + Python 3.11 + SQLite + Groq running on **Railway**
- **Frontend**: Vite + React SPA running on **Vercel**

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────┐
│                    Vercel (Frontend)                    │
│   • Vite + React SPA                                    │
│   • vercel.json SPA rewrites                            │
│   • VITE_API_BASE_URL -> https://<railway-domain>       │
└────────────────────────────┬────────────────────────────┘
                             │  HTTPS Requests (CORS protected)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                    Railway (Backend)                    │
│   • Docker container (Python 3.11-slim)                 │
│   • FastAPI serving M1–M9 API endpoints                 │
│   • Binds to 0.0.0.0:${PORT}                            │
│   • Groq LLM Provider (openai/gpt-oss-120b)             │
│   • Health check: /health                               │
│   • Railway Volume mounted at /app/storage              │
│       ├── memory.db (SQLite persistent memory)          │
│       ├── raw/ (Raw uploaded communications)            │
│       └── processed/ (Processed extraction JSONs)       │
└─────────────────────────────────────────────────────────┘
```

---

## Part 1: GitHub Preparation

Ensure your local repository contains all configuration manifests and is pushed to your GitHub repository:

```bash
git add Dockerfile .dockerignore railway.toml Procfile frontend/vercel.json app/main.py frontend/src/api/client.ts DEPLOYMENT.md
git commit -m "feat: add Railway and Vercel deployment configuration"
git push origin main
```

---

## Part 2: Railway Deployment (Backend)

### 1. Create a New Project on Railway
1. Go to [railway.com](https://railway.com/) and sign in.
2. Click **"New Project"** → **"Deploy from GitHub repo"**.
3. Select your repository (`Archscale`).
4. Railway will automatically detect the `railway.toml` and `Dockerfile` in the root directory.

### 2. Configure Persistent Volume (CRITICAL for SQLite & File Storage)
By default, Railway container filesystems are ephemeral. To ensure SQLite (`memory.db`) and uploaded files persist across redeployments:
1. In your Railway service dashboard, click on the **"Settings"** or **"Volumes"** tab.
2. Click **"Add Volume"**.
3. Set **Mount Path** to:
   ```text
   /app/storage
   ```
4. Save the volume. This ensures all database records (tasks, decisions, memory items) and raw/processed files survive server restarts and redeployments.

### 3. Configure Environment Variables
In your Railway service, navigate to the **"Variables"** tab and add the following:

| Variable | Value | Description |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `groq` | Active LLM provider |
| `LLM_MODEL` | `openai/gpt-oss-120b` | Groq model identifier |
| `GROQ_API_KEY` | `gsk_...` | Your Groq API key |
| `STORAGE_ROOT` | `/app/storage` | Path to persistent storage volume |
| `CORS_ORIGINS` | `*` *(temporarily, update after Vercel deployment)* | Allowed frontend origins |

> [!CAUTION]
> Never set `GROQ_API_KEY` on the Vercel frontend. The key must only exist on the Railway backend.

### 4. Generate Public Domain
1. In the Railway service dashboard, go to the **"Settings"** tab.
2. Scroll to the **"Public Networking"** / **"Domains"** section.
3. Click **"Generate Domain"** (e.g., `archscale-production.up.railway.app`).
4. Note this URL — you will provide it to the Vercel frontend.

### 5. Verify Backend Health
Once Railway finishes building and deploying the container, verify the health check endpoint:
```bash
curl https://<your-railway-domain>.up.railway.app/health
```
Expected response:
```json
{
  "status": "ok",
  "modules": [
    "ingestion",
    "understanding",
    "action_extraction",
    "responsibility",
    "deadline",
    "decision",
    "structured_tasks",
    "project_memory",
    "agent_query"
  ],
  "version": "2.0.0"
}
```

---

## Part 3: Vercel Deployment (Frontend)

### 1. Import Project to Vercel
1. Go to [vercel.com](https://vercel.com/) and sign in.
2. Click **"Add New..."** → **"Project"**.
3. Select your GitHub repository (`Archscale`).

### 2. Configure Build & Project Settings
In the **"Configure Project"** screen:
- **Project Name**: `archscale-frontend` (or any name)
- **Framework Preset**: `Vite`
- **Root Directory**: Click **Edit** and choose `frontend` *(CRITICAL: Archscale is a monorepo; the frontend lives in `frontend/`)*.
- **Build Command**: `npm run build` (default)
- **Output Directory**: `dist` (default)
- **Install Command**: `npm install` (default)

### 3. Add Environment Variable
In the **"Environment Variables"** section, add:

| Name | Value |
| :--- | :--- |
| `VITE_API_BASE_URL` | `https://<your-railway-domain>.up.railway.app` |

*(Note: Do not worry about trailing slashes; the frontend client automatically normalizes them).*

### 4. Deploy
1. Click **"Deploy"**.
2. Vercel will build the frontend and generate your production URL (e.g., `https://archscale-frontend.vercel.app`).

---

## Part 4: Lock Down Production CORS

Now that your Vercel frontend URL is live:
1. Return to the **Railway Dashboard** → select your backend service.
2. Open the **"Variables"** tab.
3. Update `CORS_ORIGINS`:
   ```text
   https://archscale-frontend.vercel.app
   ```
   *(If you have multiple preview domains or custom domains, separate them with commas, e.g. `https://archscale-frontend.vercel.app,https://mycustomdomain.com`)*.
4. Railway will automatically restart with the new CORS configuration.

---

## Part 5: End-to-End Pipeline Verification

Verify the entire 9-module pipeline operates cleanly between Vercel and Railway:

1. **Open Frontend**: Navigate to your deployed Vercel URL `https://archscale-frontend.vercel.app`.
2. **Select or Create Project**: Choose `villa-live-proj`.
3. **Module 1 (Ingestion)**:
   - Paste a meeting note or upload a `.txt` communication.
   - Click **"Process Communication"**.
4. **Modules 2–6 (Groq LLM Pipeline)**:
   - Verify summary, action items, responsibilities, deadlines, decisions, and approvals are extracted.
5. **Module 7 (Structured Tasks)**:
   - Verify tasks are generated and visible in the Task list.
6. **Module 8 (Memory Indexing)**:
   - Verify items are indexed into Project Memory.
7. **Module 9 (Agent Query)**:
   - In the Agent Query box, submit:
     `"who has been assigned for api routing ?"`
   - Confirm you receive a direct, grounded answer with exact quote evidence and source citations.

---

## Part 6: Persistence Verification (Restart/Redeploy Test)

To prove that the persistent volume preserves your data:

1. In the frontend, ingest a communication and verify memory items exist for `villa-live-proj`.
2. Open the **Railway Dashboard**.
3. Click the **"Restart"** button on the backend service (or trigger a Redeploy).
4. Wait for the service to return to `Active` state with health check passing.
5. Return to the Vercel frontend and refresh the page.
6. Run an agent query:
   - Query: `"who has been assigned for api routing ?"`
7. **Expected Result**:
   - The query immediately returns the grounded result from SQLite.
   - No data loss occurs because `memory.db` resides on the mounted volume `/app/storage`.
