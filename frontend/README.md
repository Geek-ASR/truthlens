# TruthLens admin dashboard

Next.js (App Router) + TypeScript client for the TruthLens fact-check
review pipeline — see [`/docs`](../docs) for the product this serves and
[`/backend`](../backend) for the API it talks to. No server-side state of
its own: this is a thin client over the FastAPI backend, authenticated
with a JWT stored in `localStorage`.

## Pages

| Route | Purpose |
|---|---|
| `/login` | email/password against `POST /api/auth/login` |
| `/` | review queue, filterable by status, with pipeline-stage counts |
| `/reels/new` | manual reel intake (URL + video upload or pasted transcript) + Analyze |
| `/reels/[id]` | transcript/OCR, extracted claims, research-again / build-carousel actions |
| `/fact-checks/[id]` | the core review screen — evidence, verdict, 4 slides, caption edit, approve/reject/publish, corrections |
| `/settings/instagram` | connected Instagram accounts + connect flow |

## Running it

```bash
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL, defaults to localhost:8000
npm run dev
```

Requires the backend running separately (`cd ../backend && uvicorn app.main:app --reload`)
against a migrated Postgres — see the top-level README for setup.

`npm run build` and `npm run lint` are both expected to pass clean before
shipping a change here.
