# Polyglot Microservice Architecture: Finance Vibe + FinSight AI

## Overview

This repo contains two services that together implement an interview-ready, production-flavored “quant + LLM” analysis pipeline:

- **Python service (Finance Vibe)**: Computes a **Composite Vibe Score** and underlying technical signals (SMA, MACD histogram, RSI, CCI) using Python’s data ecosystem.
- **Java service (FinSight AI Orchestrator)**: Orchestrates tool-driven LLM analysis (LangChain4j) and persists recommendations. Before asking the LLM for BUY/SELL/HOLD JSON, it fetches the quantitative scoring output from the Python service over HTTP.

Both services run locally under Docker Compose and communicate over Docker’s internal DNS/network.

---

## System Design: Why Python for Quant, Java for Orchestration?

### Python for data processing (Finance Vibe)
- **Best-in-class data/indicator ecosystem**: Python has mature, widely used libraries for time series + technical indicators (e.g., `pandas`, `pandas_ta`, `yfinance`).
- **Rapid iteration on math**: Indicator tuning and validation patterns (like the project’s “shadow math” approach) are easier to develop and test in Python.
- **Compute isolation**: “Heavy math” and market-data fetching are isolated behind a single API so the rest of the system is decoupled from Python-specific dependencies.

### Java for AI orchestration (FinSight AI)
- **Enterprise ergonomics**: Spring Boot provides strong foundations for API design, configuration, error handling, dependency injection, and operational readiness.
- **Reliability patterns are straightforward**: retries, fallbacks, request tracing, and structured configs are idiomatic.
- **Service composition**: the orchestrator can evolve to call multiple internal services (quant scoring, news ingestion, backtesting, etc.) without turning into a monolith.

**Separation of concerns** is the core reason: each language is used where it is strongest, and each service has a clear responsibility boundary.

---

## Inter-Process Communication (IPC): REST over Docker Internal Network

### Communication flow
1. Client triggers Java analysis (e.g., analyze ticker).
2. Java calls Python:
   - `GET http://python-scoring-service:8000/api/v1/score/{ticker}`
3. Python returns JSON:
   - `score` + `signals` (SMA, MACD hist + signal, RSI + signal, CCI + signal).
4. Java injects this JSON into the LLM system prompt as mandatory context.
5. Java then executes the LangChain4j tool-driven workflow and returns final BUY/SELL/HOLD JSON.

### Why REST?
- **Simple, debuggable, language-agnostic**: curlable endpoints, easy local testing.
- **Good boundary enforcement**: the quant service is a “black box” with a stable contract.
- **Docker-native networking**: Compose provides internal DNS (`python-scoring-service`) and isolates ports/services cleanly.

---

## Interview Talking Points: Trade-offs & Resilience

### Trade-offs vs monolith
- **Pros**
  - Independent deployability and scaling (quant service could scale separately from LLM orchestration).
  - Clear ownership boundaries (math vs orchestration).
  - Polyglot best-tool-for-the-job without infecting the whole codebase with cross-language deps.
- **Cons**
  - **Latency overhead**: one extra network hop (HTTP request) per analysis.
  - More moving parts (Docker networking, health checks, service discovery).
  - Operational complexity (observability, versioning, contract compatibility).

### Failure modes between services
Common failure cases:
- Python service down / not reachable (connection refused, DNS, startup order).
- Python returns `500` due to upstream market data issues.
- Slow responses (timeouts) due to yfinance slowness or rate limiting.

### Resilience approach implemented
- **Retry**: the Java client retries the quant call a small number of times with a short delay.
- **Fallback**: if retries fail, Java uses a structured “unavailable” quant payload and explicitly tells the LLM the quant service was unavailable.
- **Health checks + startup ordering (Compose)**:
  - Compose waits for Python `/health` and Postgres readiness before starting the Java orchestrator.

### Why this is “Google-style”
This design demonstrates:
- clear service boundaries and contracts
- reasoning about latency vs modularity
- explicit handling of partial failure (retry + degrade gracefully)
- a path to production hardening (timeouts, circuit breakers, caching, bulkheads, SLOs)

### What you’d improve next (if asked)
- Add explicit **timeouts** on the Java → Python call and tune per environment.
- Add **circuit breaker** (e.g., Resilience4j) to prevent cascading failures when Python is unhealthy.
- Add **caching** of quant responses (ticker + asOf window) to reduce repeated yfinance calls.
- Add **observability**: request IDs, metrics (p95 latency of quant calls), structured logs, and dashboards.
- Add API contract versioning (`/api/v1`) plus schema validation for backward compatibility.

---

## Local Dev: Run the Whole System

From repo root:

```bash
docker compose up --build
```

Useful endpoints:
- Python scoring: `GET /api/v1/score/AAPL` on port `8000`
- Java orchestrator: port `8080`

