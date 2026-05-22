# ArchiAI

A full-stack AI-powered architectural design platform. Describe a building in plain English and get back a bylaw-compliant room layout, PDF report, DXF file for CAD, and a real-time 3D visualisation — all in one API call.

---

## What it does

1. **Parses** a natural language brief (e.g. *"3-floor residential house on a 30×40 plot in Mumbai, north-facing"*) using a local Ollama LLM.
2. **Loads** the appropriate regional building bylaws (Mumbai DCPR, Delhi, NYC, or a conservative fallback).
3. **Checks compliance** deterministically — setbacks, FAR/FSI, floor count, height, plot coverage, and parking — with no LLM involved in the math.
4. **Retrieves** relevant architectural principles via a vectorless BM25 knowledge base.
5. **Generates** a conceptual zone layout with room dimensions and floor assignments.
6. **Places furniture** within each zone.
7. **Evaluates** Vastu Shastra preferences (optional, advisory).
8. **Exports** PDF reports, DXF files for CAD, and Hypar-compatible JSON for 3D viewers.
9. **Broadcasts** real-time progress via WebSocket as the pipeline runs.
10. **Persists** every design session and links it to a project for version history.

---

## Tech stack

### Backend

| Layer | Technology |
| --- | --- |
| Web framework | Django 5 + Django REST Framework |
| WebSockets | Django Channels + ASGI |
| Background jobs | Celery + Redis |
| Authentication | JWT via `djangorestframework-simplejwt` |
| NLP parsing | Ollama (`llama3.2` by default) |
| Knowledge retrieval | `rank-bm25` (no vector DB required) |
| PDF generation | ReportLab |
| DXF export | `ezdxf` |
| Geometry | `trimesh` |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Package manager | `uv` |
| Tests | `pytest` + `pytest-django` |

### Frontend

| Layer | Technology |
| --- | --- |
| Framework | React 19 + Vite |
| 3D rendering | Three.js |
| Routing | React Router v7 |
| HTTP client | Axios |

---

## Project structure

```text
ArchiAI/
├── backend/
│   ├── apps/
│   │   ├── accounts/       # JWT user auth (register, login, token refresh)
│   │   ├── design/         # Design pipeline, OperationJob, WebSocket consumer
│   │   ├── health/         # Health check + browser-based Design Studio
│   │   ├── projects/       # Projects, collaborators, revisions, comments
│   │   └── reports/        # PDF and DXF generation
│   ├── archi3d/
│   │   ├── settings/
│   │   │   ├── base.py     # Shared settings
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── celery.py       # Celery app config
│   │   ├── routing.py      # WebSocket URL routing
│   │   ├── urls.py         # Root HTTP URL config
│   │   └── asgi.py
│   ├── bylaws/             # Regional bylaw rulesets (JSON)
│   │   ├── default.json
│   │   ├── india_delhi.json
│   │   ├── india_mumbai.json
│   │   └── usa_nyc.json
│   ├── services/           # All business logic (no Django deps)
│   │   ├── pipeline.py           # End-to-end orchestrator
│   │   ├── input_parser.py       # Ollama NLP parser
│   │   ├── bylaw_loader.py       # Bylaw JSON loader + region detection
│   │   ├── rule_engine.py        # Deterministic compliance checks
│   │   ├── layout_generator.py   # Conceptual zone layout
│   │   ├── furniture_placer.py   # Furniture placement within zones
│   │   ├── geometry_builder.py   # Hypar JSON builder
│   │   ├── geometry_validator.py
│   │   ├── hypar_bridge.py       # Hypar cloud bridge
│   │   ├── hypar_client.py
│   │   ├── report_pdf.py         # PDF report generation
│   │   ├── dxf_exporter.py       # DXF file generation
│   │   ├── vectorless_rag.py     # BM25 knowledge retrieval
│   │   ├── knowledge_ingestion.py
│   │   ├── explanation_builder.py
│   │   ├── design_brief_builder.py
│   │   ├── background_jobs.py    # Async job management
│   │   ├── safe_web_scraper.py
│   │   └── vastu_rules.py
│   ├── scripts/            # Utility scripts (knowledge ingestion, scraping)
│   ├── tests/              # pytest test suite
│   └── manage.py
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── Landing.jsx
    │   │   └── Studio/
    │   │       ├── index.jsx
    │   │       ├── Canvas2DView.jsx
    │   │       ├── Canvas3DView.jsx  # Three.js
    │   │       ├── LeftSidebar.jsx
    │   │       ├── RightSidebar.jsx
    │   │       ├── CanvasToolbar.jsx
    │   │       └── TopBar.jsx
    │   ├── services/api.js   # Axios API client
    │   ├── utils/            # Canvas helpers, colors, element manager
    │   └── styles/
    └── package.json
```

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the React frontend)
- Redis (for Celery and Django Channels)
- [Ollama](https://ollama.com) running locally with `llama3.2` pulled

```bash
ollama pull llama3.2
redis-server  # or start via your OS service manager
```

### Backend setup

```bash
cd backend

# Install dependencies
pip install uv
uv sync

# Configure environment
cp .env.example .env  # then edit .env with your values

# Apply migrations
python manage.py migrate

# Start the server (ASGI — required for WebSockets)
python manage.py runserver
```

Key `.env` variables:

```ini
SECRET_KEY=your-secret-key-here
DEBUG=True

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2
RAG_TOP_K=5

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Optional — leave blank to skip Hypar cloud submission
HYPAR_API_URL=
HYPAR_API_TOKEN=

# Set to True to require JWT auth on POST /api/v1/design/
REQUIRE_AUTH_FOR_DESIGN=False
```

### Celery worker (for background exports)

```bash
cd backend
celery -A archi3d worker -l info
```

### Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The React app runs at `http://localhost:5173`.

---

## API reference

### Authentication — `/api/v1/auth/`

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/auth/register/` | Create a new account |
| POST | `/api/v1/auth/login/` | Obtain JWT access + refresh tokens |
| POST | `/api/v1/auth/token/refresh/` | Refresh an access token |
| POST | `/api/v1/auth/logout/` | Blacklist a refresh token |

### Design pipeline — `/api/v1/design/`

#### `POST /api/v1/design/`

Run the full pipeline. Returns a design session with compliance report, layout zones, and explanation.

**Minimum request body:**

```json
{
  "plot_width_m": 30,
  "plot_depth_m": 40
}
```

**Full request body:**

```json
{
  "raw_text": "3-floor residential house in Mumbai on a 30x40 plot, north-facing, 2 bedrooms",
  "plot_width_m": 30,
  "plot_depth_m": 40,
  "num_floors": 3,
  "num_units": 1,
  "region": "india_mumbai",
  "building_type": "residential",
  "plot_facing_direction": "north",
  "use_vastu": true
}
```

**Response (201):**

```json
{
  "session_id": "uuid",
  "status": "completed",
  "region": "india_mumbai",
  "compliance_report": {
    "is_fully_compliant": true,
    "adjusted_floors": 3,
    "required_parking_stalls": 1,
    "checks": []
  },
  "layout_zones": [
    { "room_type": "living", "floor": 0, "x": 0, "y": 0, "width_m": 5, "depth_m": 4 }
  ],
  "vastu_report": { "score": 85, "room_checks": [] },
  "explanation": "...",
  "hypar_json_path": "outputs/session_a3f91b.json",
  "requires_clarification": false
}
```

If the parser needs clarification, the response returns `"requires_clarification": true`. Answer the questions and resubmit.

#### Other design endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/v1/design/` | List last 50 sessions |
| GET | `/api/v1/design/<id>/` | Retrieve a session |
| POST | `/api/v1/design/hypar/bridge/jobs/` | Submit async Hypar export |
| GET | `/api/v1/design/jobs/<job_id>/` | Poll job status |
| GET | `/api/v1/design/jobs/` | List recent jobs |
| POST | `/api/v1/design/ingestion/jobs/` | Ingest knowledge documents |

### Projects — `/api/v1/projects/`

| Method | Endpoint | Description |
| --- | --- | --- |
| GET / POST | `/api/v1/projects/` | List or create projects |
| GET / PUT / DELETE | `/api/v1/projects/<id>/` | Retrieve, update, or delete |
| POST | `/api/v1/projects/<id>/collaborators/` | Add a collaborator (viewer / editor / admin) |
| GET | `/api/v1/projects/<id>/revisions/` | Version history |
| POST | `/api/v1/projects/<id>/comments/` | Add a comment to a revision |
| GET | `/api/v1/projects/<id>/share-link/` | Get a public share link |

### Reports — `/api/v1/reports/`

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/v1/reports/pdf/` | Generate a PDF report for a session |
| POST | `/api/v1/reports/dxf/` | Generate a DXF file for CAD |

### Health — `/api/v1/health/`

Returns `200 OK` when the server is running. Also serves the built-in browser Design Studio at `/api/v1/health/studio/`.

### WebSocket — real-time progress

Connect while a design job is running to stream progress events:

```text
ws://localhost:8000/ws/design/<job_id>/?token=<access_token>
```

Events received:

```json
{ "stage": "parsing",    "pct": 20,  "message": "Parsing input..." }
{ "stage": "compliance", "pct": 50,  "message": "Checking bylaws..." }
{ "stage": "layout",     "pct": 80,  "message": "Generating layout..." }
{ "stage": "complete",   "pct": 100, "result": {} }
```

---

## Regions and bylaws

| `region` value | Ruleset |
| --- | --- |
| `india_mumbai` | DCPR 2034 |
| `india_delhi` | Delhi building bylaws |
| `usa_nyc` | NYC Zoning Resolution |
| `default` | Conservative fallback (stricter than average) |

If no region is specified, the parser attempts to detect it from `raw_text`. To add a new region, create `bylaws/<region_id>.json` following the structure in `bylaws/default.json`.

---

## Compliance checks

The rule engine (`services/rule_engine.py`) is entirely deterministic — no LLM involved:

| Check | What it validates |
| --- | --- |
| Buildable area | Plot is large enough after setbacks |
| Floor count | Requested floors ≤ bylaw maximum |
| Height | `floors × floor_height_m` ≤ `max_height_m` |
| FAR / FSI | Total built area ÷ plot area ≤ `max_far` |
| Plot coverage | Footprint ÷ plot area ≤ `max_plot_coverage_pct` |
| Parking | Advisory — stalls = `ceil(units × min_stalls_per_unit)` |

If floors or FAR exceed the limit, `adjusted_floors` in the response shows the legal maximum.

---

## Session lifecycle

```text
received → compliance_checked → layout_generated → completed
                                                 ↘ failed
```

- `received` — clarification needed; pipeline stopped early.
- `compliance_checked` — bylaws checked but no layout zones generated.
- `layout_generated` — zones exist but geometry validation found overlaps; exports deferred.
- `completed` — full pipeline ran successfully.
- `failed` — unhandled error; see `error_message`.

---

## Running tests

```bash
cd backend
pytest
```

Test files cover accounts auth, the design API, WebSocket consumers, knowledge ingestion, pipeline services, project management, reports, and the rule engine.

---

## Django Admin

Browse all models at `http://localhost:8000/admin/` after creating a superuser:

```bash
python manage.py createsuperuser
```

---

## License

See [backend/LICENSE](backend/LICENSE).
