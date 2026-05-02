# Polyglot Quant + AI System (Finance Vibe + FinSight AI)

## What this is

This folder (`polyglot-system/`) contains **two connected projects** running as a small polyglot microservice system:

1) **Finance Vibe (Python 3.12)** — a quantitative scoring service that computes a **Composite Vibe Score** and the underlying technical signals (SMA20/50, MACD histogram + signal, RSI + signal, CCI + signal) using `yfinance`, `pandas`, and `pandas_ta`.

2) **FinSight AI (Java / Spring Boot)** — the “main orchestrator” that runs a LangChain4j tool-driven analysis and produces final **BUY/SELL/HOLD** JSON. Before it asks the LLM to decide, it calls the Python service over HTTP and injects the returned quant JSON into the LLM prompt as mandatory context.

The services communicate via **REST over Docker Compose internal networking**.

---

## Repo layout

```
polyglot-system/
  apps/
    finance-vibe/                 # Python scoring service (FastAPI + yfinance)
    financeAIAnalyzer/
      finance-ai/                 # Spring Boot orchestrator (LangChain4j)
      finance-ai-frontend/        # Optional UI (not required for the microservice demo)
  docker-compose.yml              # Runs Python + Java + Postgres together
  ARCHITECTURE.md                 # Interview-oriented system design notes
  .env.example                    # Template for secrets (copy to .env)
  .env                            # Local-only secrets (gitignored)
```

---

## How they communicate (end-to-end)

### 1) Java orchestrator requests quant data

The Spring Boot service reads:

- `QUANT_API_URL` (defaults to `http://localhost:8000` outside Docker)

and calls the Python service:

- `GET {QUANT_API_URL}/api/v1/score/{ticker}`

### 2) Python service returns a JSON payload

The Python service returns a payload shaped like:

- `score` (Composite Vibe Score)
- `signals` (SMA/MACD/RSI/CCI values)

### 3) Java injects the quant JSON into the LLM prompt

The Java service serializes the response and injects it into the LangChain4j prompt template (`prompts/stock_analyzer_prompt.txt`) as **mandatory context**, then runs the normal tool-driven analysis flow.

### 4) Resilience behavior

If Python is down / errors:

- Java retries a small number of times
- then falls back to an `"unavailable": true` quant payload
- the prompt explicitly instructs the LLM to proceed using tools and to state the quant service was unavailable

---

## Run everything with Docker (recommended)

### 1) Set environment variables

Copy the template:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `OPENAI_API_KEY=...`

(Optional, depending on which tools you use: `NEWS_API_KEY`, `FMP_API_KEY`, `ALPHAVANTAGE_API_KEY`.)

### 2) Start the system

From `polyglot-system/`:

```bash
docker compose up --build
```

### 3) Quick checks

- Python health: `http://localhost:8000/health`
- Python score: `http://localhost:8000/api/v1/score/AAPL`
- Java API: `http://localhost:8080` (see controllers under `apps/financeAIAnalyzer/finance-ai`)

Inside Docker, Java reaches Python at:

- `http://python-scoring-service:8000`

because Docker Compose provides internal DNS for service names.

---

## Run services individually (dev)

### Python scoring service

From `apps/finance-vibe/`:

```bash
pip install -r requirements.txt
python main.py
```

It serves on port `8000`.

### Java orchestrator

From `apps/financeAIAnalyzer/finance-ai/`:

```bash
./mvnw spring-boot:run
```

If you’re running locally (not Docker), ensure:

- `QUANT_API_URL=http://localhost:8000`

and Postgres is available (or update Spring datasource properties accordingly).

---

## Where to look in code

### Python
- API entrypoint: `apps/finance-vibe/main.py`
- Quant computation wrapper: `apps/finance-vibe/src/finance_vibe/scoring_service.py`
- Existing math engine: `apps/finance-vibe/src/finance_vibe/analysis_engine.py` (`calculate_composite_vibe`)

### Java
- Quant HTTP client: `apps/financeAIAnalyzer/finance-ai/src/main/java/com/sheel/finance_ai/quant/QuantitativeScoringClient.java`
- Prompt injection point: `apps/financeAIAnalyzer/finance-ai/src/main/java/com/sheel/finance_ai/ai/AgentService.java` (`runFullAnalysis`)
- Prompt template: `apps/financeAIAnalyzer/finance-ai/src/main/resources/prompts/stock_analyzer_prompt.txt`

---

## Architecture / interview notes

See `ARCHITECTURE.md` for:
- why this is split into Python + Java services
- REST IPC details
- trade-offs (latency vs modularity)
- resilience discussion (retry/fallback) and next hardening steps

