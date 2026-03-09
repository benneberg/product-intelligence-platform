# Product Intelligence Platform

AI-driven synthetic users for automated UX analysis.

## Overview

The Product Intelligence Platform uses AI-driven synthetic users to automatically analyze web application usability and generate actionable UX insights.

**MVP Feature**: Submit a URL → AI agent explores it like a real user → Receive detailed UX analysis report

## Architecture

```
┌─────────────────────────────────────────────────┐
│ Web UI (FastAPI)                                │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│ Orchestrator (Simulation Manager)               │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│ ⭐ SIMULATION ENGINE (Core) ⭐                  │
│ • State management                              │
│ • Loop control                                  │
│ • Termination detection                         │
└────────┬────────────────────────────────────────┤
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────────┐
│ Agent │ │ Browser   │
│Controller│ │Automation│
└───────┘ │ (Playwright)│
    └───────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌──────────┐
│ LLM   │ │ Target   │
│(GPT-4)│ │ Website  │
└───────┘ └──────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### Setup

1. **Clone and navigate to project:**
   ```bash
   cd product-intelligence-platform
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start services:**
   ```bash
   docker-compose up -d
   ```

4. **Check status:**
   ```bash
   docker-compose ps
   ```

5. **Access the API:**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/docs

### Run Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "persona": "curious_beginner"}'
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/analyze` | Create analysis job |
| GET | `/api/v1/jobs` | List all jobs |
| GET | `/api/v1/jobs/{job_id}` | Get job status |
| GET | `/api/v1/jobs/{job_id}/report` | Get UX report |
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects` | List projects |

## Development

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

3. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Start API:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Start worker:**
   ```bash
   celery -A app.worker.celery_app worker --loglevel=info
   ```

### Running Tests

```bash
pytest tests/
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | postgresql+asyncpg://... |
| `CELERY_BROKER_URL` | Redis broker URL | redis://redis:6379/0 |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `HEADLESS` | Run browser in headless mode | true |
| `MAX_STEPS` | Maximum simulation steps | 50 |
| `MAX_DURATION_SECONDS` | Max simulation duration | 900 |

## Project Structure

```
product-intelligence-platform/
├── app/
│   ├── api/           # API routes
│   ├── core/          # Core business logic
│   │   ├── browser.py     # Playwright automation
│   │   ├── engine.py     # Simulation engine
│   │   └── llm.py       # LLM client
│   ├── db/            # Database layer
│   ├── schemas/       # Pydantic schemas
│   ├── worker/        # Celery tasks
│   ├── config.py      # Settings
│   └── main.py        # FastAPI app
├── alembic/           # Database migrations
├── docker/            # Dockerfiles
├── docker-compose.yml
├── requirements.txt
└── .env
```

## License

MIT License
