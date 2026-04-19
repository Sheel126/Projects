# Projects

# 📈 FinSight AI
An agentic AI-powered investment assistant that autonomously analyzes stocks and provides structured investment recommendations.

### 🛠️ Tech Stack
- Backend: Java (Spring Boot)
- AI Framework: LangChain4j
- LLM: OpenAI API
- Database: PostgreSQL
- Frontend: React, Tailwind CSS

### 🚀 Features
- **Agentic AI System** – Autonomously invokes multiple tools (real-time price data, historical trends, news sentiment, trending tickers) to analyze stocks
- **Tool-Driven LLM Pipeline** – Uses LangChain4j to enforce deterministic JSON outputs with BUY/SELL/HOLD signals, investment horizons, predicted gains, confidence scores, and AI-generated reasoning
- **Multi-Ticker Batch Analysis** – Automatically fetches trending stocks, runs parallel AI analysis on each, and persists recommendations with retry logic and validation
- **Memory-Aware Agents** – Retains past analyses to improve contextual reasoning and recommendation consistency across user sessions
- **RESTful API** – Exposes endpoints for real-time single-stock analysis and batch processing with comprehensive error handling and resilience patterns
- **Interactive Dashboard** – React + Tailwind UI allowing users to browse trending stocks, trigger on-demand AI analysis, and view recommendations with confidence metrics and source links
- **Enterprise Architecture** – Follows layered design, repository pattern, service abstraction, DTO validation, and configuration-based CORS handling

### 🏗️ Architecture
- Implements enterprise backend practices including layered architecture and repository pattern
- Structured validation before database persistence
- Configuration-based security and CORS handling
- Proper error handling and retry mechanisms for external API calls

---

# 🏃 MoveMate
A full-featured goal-tracking Progressive Web App (PWA) designed to keep users motivated and organized.

### 🛠️ Tech Stack
- Backend: Node JS
- Frontend: JS
- Database: MariaDB
- Authentication: JWT (JSON Web Tokens)
- Deployment: Docker, Docker Compose
- PWA Features: Service Workers, App Manifest, Offline Caching

### 🚀 Features
- User Authentication – Secured login system using JWT for token-based authentication and authorization.
- Goals Dashboard – Track progress, edit targets, and manage goal-related items by category.
- User Streaks – Visualize ongoing streaks to maintain momentum and motivation.
- Reminders – Set custom reminders, track history, and manage alerts.
- AI Recommendations – Get personalized suggestions based on user activity and preferences.
- Offline Support – PWA capabilities allow users to view goals, reminders, and recommendations offline.
- Dockerized Setup – Easily build and run the app using `docker compose build` and `docker compose up`.

### 👥 Collaboration
- Worked on a cross-functional team.
- Followed Agile methodology with sprint planning and weekly stand-ups.

---

# 🌱 EDUSustainabilityLab
A full-stack web application enabling teachers to create, post, and manage sustainability-focused student activities.

### 🛠️ Tech Stack
- Backend: Python (Django)
- Frontend: React
- Database: MySQL

### 🚀 Features
- Teacher dashboard to create, post, and manage sustainability activities  
- Persistent data storage and retrieval  
- Agile development with sprint planning and daily stand-ups  
- Industry-sponsored real-world project collaboration

### 👥 Collaboration
- Worked on a cross-functional, industry-sponsored team.
- Followed Agile methodology with sprint planning and daily stand-ups.

---

# 🧠 AI-Powered Chip's Challenge Bot
An AI-powered bot that autonomously solves levels in the classic puzzle game **Chip's Challenge**.

### 🤖 Key Concepts
- Implemented the **A\*** search algorithm and intelligent pathfinding.
- Used heuristics, state-space search, and problem decomposition.
- Designed for adaptability to various level configurations.

### 🚀 Features
- Autonomous game bot solving Chip's Challenge levels  
- Intelligent pathfinding using A* search algorithm  
- State-space search and problem decomposition  
- Adaptable to multiple level configurations  

---

# 🐙 GitHub Clone
A full-stack web application modeled after modern version control platforms, built as part of a collaborative school club project.

### ⚙️ Tech Stack
- Backend: .NET
- Frontend: Custom
- Database: MySQL
- Containerized: Docker

### 🚀 Features
- Full-stack repository hosting platform  
- Fetch and display user repositories from backend  
- Collaborative large-scale team development  
- Modeled after modern version control systems 

### 🔧 Contributions
- Built a component that fetches and displays user repositories from the backend.

---

# ☕ CoffeeMaker
A web application to simulate and manage coffee making preferences.

### ⚙️ Tech Stack
- Frontend: Angular
- Backend: Java (Spring Boot)
- ORM: Hibernate
- Database: MySQL

### 🚀 Features
- Interactive coffee maker UI with Angular  
- User preferences and transaction history stored in MySQL  
- Robust backend for data management with Hibernate ORM  
- Seamless frontend-backend integration  

### 🤝 Team Effort
- Integrated front-end and back-end systems for improved performance and workflow.

---

# 🔐 C Encryption/Decryption Project
A C-based project implementing custom encryption and decryption logic for secure message handling.

### 🚀 Features
- Low-level string and memory manipulation  
- Hands-on cryptography implementation
# Finance Vibe 📈

## Trader-first docs (start here)

If you’re using this as a trader and want the outputs to “make sense” (without caring about the code), read:

- `TRADER_GUIDE.md`

## Project Intent & Engineering Philosophy

The **Finance Vibe** project is engineered as a **Modular Data Pipeline**.  
The intent is to transition from isolated "scripts" to a **Systematic Analysis Engine**.

By decoupling **data ingestion**, **mathematical processing**, and **reporting layers**, we ensure the system is:

- Idempotent
- Scalable
- Reproducible

This project prioritizes:

- **Environmental Parity**
- **Mathematical Robustness**

The system operates within a stable **5-year weekly regime** to eliminate high-frequency noise and ensure reproducible results across any compute node.

---

## Key Architectural Decisions

### Hermetic Environment (Dev Containers)

We utilize **Docker-based Dev Containers** to enforce _Environment-as-Code_.

This approach:

- Locks the Python 3.12 interpreter
- Locks system dependencies
- Stores environment configuration in version control

The environment becomes a **disposable, reproducible artifact**.

---

### Stateless Logic & State Isolation

The repository architecture enforces a strict boundary between:

- `/src/` — Application logic
- `/data/` — System state

Within `/data/`:

- `/raw/` — Immutable source data
- `/logs/` — Analytical output

This isolation ensures:

- The pipeline can be audited independently
- Data can be wiped without risking the codebase
- Code and state remain cleanly separated

---

### Shadow Math (Architectural Redundancy)

The system implements a **Dual-Engine Pattern** for logic verification.

A **Shadow Engine** (`analysis_engine_local.py`) runs alongside the primary engine to enable:

- Differential testing
- Safe mathematical experimentation
- Validation of scoring changes

This is particularly important for validating our **Manual Mean Absolute Deviation (MAD)** implementation before promoting changes to the main pipeline.

---

### Decoupled Orchestration

`run_vibe.py` functions as a **Stateless Orchestrator**.

It manages the lifecycle:

```
Discovery → Ingestion → Analysis → Comparison
```

This design allows:

- Execution via external schedulers (Cron / GitHub Actions)
- Clear exit codes for failure handling
- Clean separation between orchestration and computation

## Strategic Trend & Momentum Pipeline

A professional-grade Python framework for fetching and analyzing stock data from Yahoo Finance.

This project uses a **Composite Vibe Score** to identify high-conviction trends using weekly data science workflows.

---

# 🏗 Project Structure

```
src/finance_vibe/
```

### Core Python Logic

- **config.py** — Central settings (5y weekly data, ETFs, paths)
- **ticker_provider.py** — Refreshes active stocks & benchmark ETFs (SPY, QQQ, IWM)
- **data_ingestor.py** — Pulls 5-year weekly historical data
- **analysis_engine.py** — Primary math engine (SMA, MACD, RSI, Robust CCI)
- **analysis_engine_local.py** — Shadow engine for validation
- **swing_scanner.py** — Filters valid swing trade setups using EMA, RSI, ATR, and MACD
- **trade_planner.py** — Generates detailed trade plans including stock entries, stops, targets, and LEAPS options recommendations
- **run_vibe.py** — Master orchestrator to execute the full pipeline

```
data/
```

- **raw/** — Original CSV files (Ignored by Git)
- **logs/** — Archive for dated Vibe Reports (CSV format)

```
notebooks/
```

- Jupyter notebooks for data exploration

---

# 🚀 How to Use

## Run in Github CodeSpaces

- Easiest way to run and try it out is github codespaces
- See documents attached in repo
- https://github.com/jigar3730/finance-vibe/blob/main/How%20to%20run%20in%20Github%20codespaces.docx

## 1️⃣ Open in Dev Container

Ensure Docker is running.

Reopen the project in the container to auto-install:

- Python 3.12
- Pandas
- Required extensions (Rainbow CSV, Excel Viewer)

---

## 2️⃣ Run the Pipeline

Execute the master command to ingest data and run analysis:

```bash
python src/finance_vibe/run_vibe.py
```

### Optional AI Review Step

If you want an AI-written review for each trade-plan row, run:

```bash
python src/finance_vibe/ai_reviewer.py
```

This reads the latest trade plan in `data/logs/`, optionally enriches it with news/event data, and writes:

- `data/logs/trade_plan_ai_YYYY-MM-DD.csv`
- `data/logs/trade_plan_ai_YYYY-MM-DD.json`

You can also enable this automatically at the end of the main pipeline:

```bash
FINANCE_VIBE_ENABLE_AI_REVIEW=1 python src/finance_vibe/run_vibe.py
```

---
## 📊 Finance Vibe Pipeline Overview

The pipeline runs as a **modular data workflow** from raw data to actionable trade plans:

1. **Raw Data** (`data/raw/`)  
   - Contains 5-year weekly OHLCV CSV files for all tracked tickers.

2. **Ticker Provider** (`ticker_provider.py`)  
   - Refreshes the list of active tickers and benchmarks (SPY, QQQ, IWM).

3. **Data Ingestor** (`data_ingestor.py`)  
   - Pulls historical data for all tickers.  
   - Saves updated CSV files in `/data/raw/`.

4. **Primary Engine** (`analysis_engine.py`)  
   - Calculates SMA20, SMA50, MACD Histogram, RSI, and Robust CCI.  
   - Generates the **Composite Vibe Score** for each ticker.

5. **Shadow Engine** (`analysis_engine_local.py`)  
   - Runs a secondary/local calculation to verify the primary engine.  
   - Ensures scoring consistency and safe experimentation.

6. **Swing Scanner** (`swing_scanner.py`)  
   - Filters tickers for actionable setups:  
     - **SETUP_LONG**: Pullbacks into EMA20 with bullish momentum.  
     - **SETUP_SHORT**: Pullbacks into EMA20 with bearish momentum.  
   - Generates a **swing setups CSV** (`data/logs/swing_setups_YYYY-MM-DD.csv`) for review.

7. **Trade Planner** (`trade_planner.py`)  
   - Reads the filtered swing setups.  
   - Calculates **entry, exit, stop-loss**, and **LEAPS options** for each setup.  
   - Outputs the **final trade plan CSV** (`data/logs/trade_plan_YYYY-MM-DD.csv`).

---

**Summary:**  
- This pipeline ensures a **transparent, reproducible, and auditable workflow**.  
- Each stage produces outputs that feed the next stage, allowing clear **traceability from raw data → Vibe → Swing Setups → Trade Plan**.  
- The modular design makes it easy to **extend, test, or automate** in a Dockerized environment.

## 3️⃣ Reset Data

To clear out old raw files and force a fresh fetch:

```bash
rm data/raw/*.csv
````

---

# 📈 Technical Logic: The Composite Vibe Score

The core **Actionable Logic** is driven by a **Weighted Scoring System (-10 to +10)** to identify trend strength and momentum confluence.

---

## 📊 Scoring Matrix

| Indicator        | Logic                                                                 | Weight          |
|-----------------|----------------------------------------------------------------------|----------------|
| **Trend**        | Price in pullback zone near EMA20 **and** EMA50 is rising             | ±4.0 Points    |
| **Momentum**     | MACD Histogram rising over last 2 bars (“momentum hook”) **and** RSI above/below EMA signal | ±3.0 Points    |
| **Volatility**   | Robust CCI > 0 and above its 20-EMA for longs, < 0 for shorts        | ±3.0 Points    |
| **RSI Confluence** | RSI in optimized range: 50–65 for long pullbacks, 35–50 for shorts | ±2.0 Points    |
| **Pullback Quality** | Price not too far above EMA20 (e.g., ≤2% above) for long, or ≤2% below for short | ±2.0 Points    |

---

## 🎯 Action Tiers & Sentiment Mapping (Updated)

The `sentiment_action(score: int)` function maps the **Composite Vibe Score** to clear trading guidance:

| Score Range | Sentiment  | Action Description                       | Notes |
|-------------|-----------|-----------------------------------------|-------|
| 9+          | Bullish   | 🟢 STARTER + ADD ON PULLBACK            | Strong pullback near EMA20, EMA50 rising, momentum hook confirmed, RSI optimal |
| 7 – 8       | Bullish   | 🟢 STARTER POSITION                      | Pullback in zone, trend mostly bullish, momentum improving |
| 5 – 6       | Positive  | 📈 WATCH / SCALE IN                      | Minor pullback, trend positive, momentum emerging |
| 2 – 4       | Neutral   | ⏳ WAIT                                  | Pullback not ideal, EMA50 slope weak, momentum unclear, RSI moderate |
| -1 – 1      | Neutral   | 💤 NO EDGE                               | Market indecisive, no clear bias |
| -4 – -2     | Bearish   | 🟠 REDUCE / HEDGE                        | Weakening trend, EMA50 flat/declining, momentum negative |
| < -4        | Bearish   | 🔴 AVOID / SHORT BIAS                     | Strong bearish confluence, trend down, momentum confirmed |

**Key Points:**

1. **Bullish tiers** encourage scaling in and adding on pullbacks when trend and momentum align.  
2. **Neutral tiers** indicate indecision — best to wait or hold cash.  
3. **Bearish tiers** signal reducing positions or considering short bias.  
4. The function integrates **EMA slope, pullback zones, MACD momentum hooks, and RSI ranges** for precise decision-making.

---

# 🛠 Project Standards

## Robust CCI Calculation

Uses a manual **Mean Absolute Deviation (MAD)** formula to prevent extreme values (-4000+) during low-volatility periods.

## Data Transparency

Reports include the raw indicator values (SMA20, CCI, RSI, etc.) alongside the final score for manual verification.

## Archive Logic

Every run generates a timestamped CSV in:

```
data/logs/
```

for historical tracking.

---

# 📝 Future Roadmap

- [ ] **Automation** — Set cron to execute `run_vibe.py` every Saturday at 09:00
- [ ] **Alerting** — Integrate Discord/Telegram Webhooks for high-score signals
- [ ] **Visualization** — Add Matplotlib logic to generate "Vibe Charts" (Price vs. Score)
