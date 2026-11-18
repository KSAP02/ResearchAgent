# Project Scaffold Recipe: LangChain/LangGraph Agent as a Service

How this repo was scaffolded, so the same layout can be reused for a new
LangChain/LangGraph agent project. Follow the steps in order: at the end you
have a FastAPI backend running a LangGraph `StateGraph`, a TypeScript (React +
Vite) frontend, Milvus Lite + SQLite storage, and a `docker-compose` stack that
runs it all, verified end to end with stub nodes before any LLM code is written.

---

## 1. Stack

| Layer           | Choice                                   | Why |
|-----------------|------------------------------------------|-----|
| Agent graph     | LangGraph (`StateGraph`) + LangChain core | Shared state, conditional edges, cycles |
| Backend API     | FastAPI + Uvicorn                        | Frontend calls it over HTTP |
| Vector DB       | Milvus Lite (`pymilvus` + `milvus-lite`)  | Single local file, no server |
| SQL DB          | SQLite (stdlib `sqlite3`)                | Single local file, zero setup |
| Frontend        | React + TypeScript + Vite                | Built to static files, served by nginx |
| Containers      | Docker + docker compose                  | One command runs both services |

## 2. Final layout

```text
<project>/
├── backend/
│   ├── app.py                 # FastAPI entry point (uvicorn app:app)
│   ├── config.py              # pydantic-settings; env vars + data paths
│   ├── schemas.py             # API request/response models
│   ├── agents/                # one file per graph node
│   │   ├── planner.py
│   │   ├── researcher.py      # researcher + retriever nodes
│   │   ├── analyst.py
│   │   ├── fact_checker.py    # evidence checker (drives the retry loop)
│   │   └── reporter.py
│   ├── tools/                 # plain functions the agents call
│   │   ├── arxiv_search.py
│   │   ├── pdf_extractor.py
│   │   └── vector_retriever.py
│   ├── graph/
│   │   ├── state.py           # TypedDict shared state
│   │   └── workflow.py        # StateGraph, edges, conditional routing
│   ├── db/
│   │   ├── sqlite.py          # run history
│   │   └── vector_store.py    # Milvus Lite client + collection init
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   └── api/client.ts      # typed fetch wrapper for /api/*
│   ├── index.html
│   ├── package.json / package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts         # dev proxy /api -> localhost:8000
│   ├── nginx.conf             # prod proxy /api -> backend:8000
│   ├── Dockerfile
│   └── .dockerignore
├── data_warehouse/            # local Milvus Lite + SQLite files (git-ignored)
│   └── .gitkeep
├── MD_files/                  # briefs / docs
├── docker-compose.yml
├── .env.example               # committed; .env is not
├── .gitignore
└── README.md
```

Every `agents/`, `tools/`, `graph/`, `db/` folder gets an empty `__init__.py`.

## 3. Step by step

### Step 1: Root files

```bash
mkdir -p backend/{agents,tools,graph,db} frontend/src/api data_warehouse MD_files
touch backend/{agents,tools,graph,db}/__init__.py data_warehouse/.gitkeep
```

**`.gitignore`**: create it *first*, before any `.env` exists:

```gitignore
.env
.env.*
!.env.example
data_warehouse/*
!data_warehouse/.gitkeep
__pycache__/
*.py[cod]
.venv/
node_modules/
dist/
```

**`.env.example`**: every variable the backend reads, no real values:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=
MAX_RESEARCH_RETRIES=2
# DATA_DIR=            # unset locally -> <repo>/data_warehouse; compose sets /data
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Step 2: Backend config (`backend/config.py`)

- `pydantic-settings` `BaseSettings` reads env vars (case-insensitive) and `.env`.
- `data_dir` defaults to `Path(__file__).resolve().parent.parent / "data_warehouse"`
  so local runs write into the repo's `data_warehouse/`; Docker overrides it with
  `DATA_DIR=/data`.
- Derived properties: `sqlite_path = data_dir / "app.db"`,
  `milvus_uri = str(data_dir / "milvus.db")`.
- `get_settings()` is `@lru_cache`d and does `data_dir.mkdir(parents=True, exist_ok=True)`.

### Step 3: Storage (`backend/db/`)

- `sqlite.py`: `get_conn()` context manager (commit + close), `init_db()` runs
  `CREATE TABLE IF NOT EXISTS`, plus `save_run()` / `list_runs()`.
- `vector_store.py`: `MilvusClient(settings.milvus_uri)` (a file path makes it
  Milvus Lite), cached with `@lru_cache`; `init_vector_store()` creates the
  collection with a fixed `dimension` if it doesn't exist. Set the dimension to
  match the embedding model (384 for `all-MiniLM-L6-v2`).

### Step 4: Graph (`backend/graph/`)

- `state.py`: a `TypedDict(total=False)` holding everything nodes share
  (question, queries, papers, passages, analysis, evidence flags,
  `retry_count`, `max_retries`, report).
- `workflow.py`: `build_graph()` registers nodes, adds linear edges, and one
  `add_conditional_edges` from the checker:

```python
def route_after_check(state):
    if state.get("evidence_sufficient"):
        return "report"
    if state.get("retry_count", 0) >= state.get("max_retries", 2):
        return "report"          # hard cap: never loop forever
    return "researcher"
```

Flow: `START → planner → researcher → retriever → analyst → evidence_checker →
(researcher | report) → END`.

### Step 5: Nodes and tools as stubs

Each node is `def x_node(state) -> dict` returning **only the keys it updates**.
Write them as deterministic stubs first (no LLM, no network) so the whole stack
can be built and tested in Docker before any real logic. The checker stub
returns "insufficient" on the first pass so the retry loop gets exercised.
Then replace the stubs one at a time.

### Step 6: API (`backend/app.py`)

- A `lifespan` context manager calls `init_db()` and `init_vector_store()` on startup.
- Compile the graph once at import: `graph = build_graph()`.
- Routes (all under `/api` so one proxy rule covers them):
  - `GET  /api/health`: status + DB info (used by the compose healthcheck)
  - `POST /api/research`: `graph.invoke({...})`, save run to SQLite, return result
  - `GET  /api/runs`: run history
- Wrap `graph.invoke` in try/except → `HTTPException(500)`.
- `CORSMiddleware` with origins from settings (only needed for non-proxied dev).

### Step 7: Backend container

`backend/requirements.txt`:
```text
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.9
pydantic-settings>=2.6
langchain-core>=0.3
langgraph>=0.2
pymilvus>=2.5
milvus-lite>=2.4
```

`backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore`: `__pycache__/`, `*.pyc`, `.venv/`, `.env`.

### Step 8: Frontend

Hand-written minimal Vite + React + TS (no template generator needed):

- `package.json`: deps `react`, `react-dom`; devDeps `vite`, `@vitejs/plugin-react`,
  `typescript`, `@types/react`, `@types/react-dom`; script `"build": "tsc -b && vite build"`.
- `tsconfig.json`: `"moduleResolution": "bundler"`, `"jsx": "react-jsx"`,
  `"strict": true`, `"noEmit": true`, `"types": ["vite/client"]`, `"include": ["src"]`.
- `vite.config.ts`: dev server proxy `"/api" → "http://localhost:8000"`.
- `src/api/client.ts`: typed interface mirroring the backend response model;
  calls **relative** `/api/...` URLs, which works in both dev (Vite proxy) and
  Docker (nginx proxy).
- Run `npm install` once locally to generate `package-lock.json` (needed by `npm ci`).

`frontend/nginx.conf`:
```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;
    location /api/ {
        proxy_pass http://backend:8000;   # compose service name
        proxy_read_timeout 300s;          # agent runs are slow
    }
    location / { try_files $uri /index.html; }
}
```

`frontend/Dockerfile` (multi-stage):
```dockerfile
FROM node:22-slim AS build        # NOT alpine, see Gotchas
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

`.dockerignore`: `node_modules/`, `dist/`, `.env`.

### Step 9: `docker-compose.yml`

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file:
      - path: .env
        required: false        # fresh clones work without .env
    environment:
      DATA_DIR: /data
    volumes:
      - research_data:/data    # Milvus Lite + SQLite persist here
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on:
      backend:
        condition: service_healthy

volumes:
  research_data:
```

### Step 10: Verify

```bash
docker compose up -d --build
curl localhost:3000/api/health                       # through nginx -> backend
curl -X POST localhost:3000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question":"Graph RAG retrieval accuracy"}'   # expect retry_count=1
docker compose restart backend && curl localhost:8000/api/runs   # run persisted
```

Open http://localhost:3000 for the UI, and http://localhost:8000/docs for the
FastAPI Swagger UI.

## 4. Data locations

| Mode              | DATA_DIR                    | Files |
|-------------------|-----------------------------|-------|
| Local (no Docker) | `<repo>/data_warehouse/`    | `app.db`, `milvus.db` |
| docker compose    | `/data` → volume `<project>_research_data` | same |

Wipe Docker data: `docker compose down -v`.

## 5. Gotchas hit while scaffolding

1. **Alpine breaks the Vite build.** On `node:22-alpine`, `vite build` fails with
   `Code is nested too deeply ... react-dom/client.js`. Rollup's native parser
   overflows musl's small default thread stack. Use `node:22-slim` for the
   build stage (nginx alpine for serving is fine).
2. **Milvus Lite has no Windows wheels.** It runs on Linux/macOS only.
   Convention for this project: the backend runs and is tested **only inside
   Docker**, never directly on the host.
3. **Git Bash rewrites container paths.** `docker compose exec backend ls /data`
   becomes `C:/Program Files/Git/data`. Prefix with `MSYS_NO_PATHCONV=1`.
4. **`env_file` must be optional** (`required: false`, Compose ≥ 2.24) or a
   fresh clone without `.env` won't start.
5. **Keep every API route under `/api`** so a single nginx `location /api/` and a
   single Vite proxy rule cover them, and the frontend never needs absolute URLs.
6. **Commit `package-lock.json`**: the frontend Dockerfile uses `npm ci`.

## 6. Reusing for a new agent

1. Copy this layout; rename the nodes in `agents/` and the fields in `graph/state.py`.
2. Keep the stub-first approach: get `docker compose up` + an end-to-end curl
   passing with stubs, then replace stubs one node at a time, re-testing after each.
3. Rename the compose volume and Milvus collection to match the new project.
