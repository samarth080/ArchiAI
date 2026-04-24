# ArchiAI

An explainable, bylaw-aware architectural design backend that generates building layouts by combining natural language parsing, deterministic compliance checking, and spatial optimization.

## What it does

ArchiAI takes a natural language design request (e.g. "3BHK residential, 2400 sqft, Bangalore") and runs it through an end-to-end pipeline:

1. **Parses** the request using optional LLM (Ollama) with a deterministic fallback — a clarification gate blocks generation until all critical fields are resolved
2. **Retrieves** relevant bylaws using vectorless RAG (BM25 lexical scoring + metadata boosts — no embeddings needed)
3. **Checks compliance** deterministically in code — setbacks, floor area ratios, parking — never delegated to a model
4. **Synthesizes a layout** with adjacency awareness, circulation scoring, and quality metrics
5. **Exports** to Hypar-compatible JSON/CSV for downstream 3D tooling
6. **Optionally scores** Vastu alignment (cultural preference constraints, safety/legality always takes priority)
7. **Explains** every compliance decision in a structured audit trail stored in a `DesignSession`

## Tech stack

| Layer | Tech |
| --- | --- |
| Web framework | Django 5.1 + Django REST Framework |
| LLM (optional) | Ollama (local inference) |
| Search/retrieval | BM25 via `rank-bm25` |
| 3D geometry | `trimesh` + NumPy |
| Data validation | Pydantic |
| HTTP client | `httpx` |
| Testing | pytest + pytest-django |
| Package manager | `uv` |
| Database | SQLite (dev) |

## Project structure

```text
apps/
  design/        # Core design pipeline — views, models, serializers
  health/        # Health check endpoint
archi3d/         # Django project config (settings, urls, wsgi)
services/        # Business logic: parsing, retrieval, compliance, layout synthesis
knowledge/       # Bylaw documents and knowledge base
scripts/         # Ingestion and utility scripts
tests/           # Test suite
outputs/         # Generated layout outputs
```

## API endpoints

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| `POST` | `/api/v1/design/` | Run the full design pipeline, returns compliance report + layout zones |
| `GET` | `/api/v1/design/` | List the 50 most recent design sessions |
| `GET` | `/api/v1/design/<id>/` | Retrieve a specific design session |
| `POST` | `/api/v1/design/hypar/bridge/` | Export layout zones as Hypar-compatible CSV |

## Getting started

**Prerequisites:** Python 3.10+, `uv`, and optionally [Ollama](https://ollama.ai) for LLM-assisted parsing.

```bash
# Clone and install
git clone https://github.com/samarth080/ArchiAI.git
cd ArchiAI
uv sync

# Configure environment
cp .env .env.local  # edit as needed

# Run migrations and start
uv run python manage.py migrate
uv run python manage.py runserver
```

**Run tests:**

```bash
uv run pytest
```

**With Ollama (optional):**

```bash
ollama pull mistral   # or whichever model you configure
ollama serve
```

If Ollama is not running, the pipeline falls back to deterministic parsing automatically.

## Design principles

- **Deterministic compliance over AI reasoning** — bylaws are enforced in code, not prompted
- **Thin views, fat services** — views handle HTTP concerns; all business logic lives in `services/`
- **Vectorless RAG** — BM25 + metadata boosts keep retrieval fast and interpretable without a vector DB
- **Explainability first** — every layout output includes a compliance report with trade-off summaries

## License

MIT
