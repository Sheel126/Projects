# Projects

## finance-vibe (Paper Trading Bot — daily-active)

Automated Alpaca paper trading bot with Finance-Vibe signals, local Ollama LLM decisions, VWAP/IBS intraday rotation, and a live dashboard.

- **Location:** `finance-vibe/`
- **Quick start:** `finance-vibe/start-paper-bot.ps1` (Windows, before 9:30 AM ET)
- **Setup guide:** `finance-vibe/user.md`
- **Architecture:** `finance-vibe/architecture.md`

## Polyglot system (Finance Vibe + FinSight AI)

The combined microservice architecture lives in `polyglot-system/`.

- Start here: `polyglot-system/README.md`
- Architecture notes: `polyglot-system/ARCHITECTURE.md`

# 📊 Finance Vibe
A modular Python pipeline that fetches stock data from Yahoo Finance and scores each ticker using a **Composite Vibe Score** to surface high-conviction swing trade setups.

### 🛠️ Tech Stack
- Language: Python 3.12
- Data: Yahoo Finance (yfinance)
- Environment: Docker Dev Containers
- Notebooks: Jupyter

### 🚀 Features
- **Composite Vibe Score** – Weighted scoring system (-10 to +10) combining Trend, Momentum (MACD), Volatility (Robust CCI), RSI Confluence, and Pullback Quality
- **Modular Pipeline** – Decoupled stages: Ticker Provider → Data Ingestor → Analysis Engine → Swing Scanner → Trade Planner
- **Swing Scanner** – Filters tickers for actionable long/short setups based on EMA, RSI, ATR, and MACD signals
- **Trade Planner** – Generates entry, stop-loss, target, and LEAPS options recommendations per setup
- **Shadow Engine** – Dual-engine validation pattern for safe mathematical experimentation before promoting changes
- **AI Review Step** – Optional AI-written review for each trade plan row, outputting enriched CSV and JSON reports
- **Hermetic Environment** – Docker Dev Containers lock Python 3.12 and all dependencies for full reproducibility

### 👥 Collaboration
- Collaborative project with contributions to key features of the pipeline.

---

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

---
