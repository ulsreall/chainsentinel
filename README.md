# 🛡️ ChainSentinel

**AI-Powered Smart Contract Security Platform** — Multi-agent analysis pipeline using Xiaomi MiMo

![ChainSentinel](https://img.shields.io/badge/AI-MiMo%20v2.5-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tokens](https://img.shields.io/badge/daily%20tokens-5M%2B-orange)

## Overview

ChainSentinel is a production-grade smart contract security audit platform that uses **multiple specialized AI agents** to perform comprehensive code analysis. Built on top of Xiaomi MiMo's reasoning models, it orchestrates a 4-stage analysis pipeline that naturally consumes millions of API tokens per day.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    ChainSentinel                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Vuln     │  │ Gas      │  │ Logic    │  │ Report │ │
│  │ Scanner  │  │ Optimizer│  │ Auditor  │  │ Writer │ │
│  │ (Agent 1)│  │ (Agent 2)│  │ (Agent 3)│  │(Agent 4)│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘ │
│       │              │              │             │      │
│       └──────────────┼──────────────┘             │      │
│                      │                            │      │
│               ┌──────▼──────┐              ┌──────▼────┐ │
│               │  Preprocess │              │ Synthesis │ │
│               │  & Chunking │              │  & Report │ │
│               └─────────────┘              └───────────┘ │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │              MiMo API (OpenAI-compatible)            ││
│  │         Token Tracking & Budget Management          ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

## 🔥 Why It Consumes Millions of Tokens Daily

### 1. Multi-Agent Architecture
Each contract audit runs **4 specialized agents** in sequence:
- **Vulnerability Scanner**: Reentrancy, overflow, access control, oracle manipulation
- **Gas Optimizer**: Storage layout, loop optimization, assembly opportunities
- **Logic Auditor**: MEV vectors, price manipulation, governance attacks
- **Report Generator**: Professional audit report with severity ratings

### 2. Chunked Analysis for Large Contracts
Contracts over 200 lines are split into overlapping chunks, analyzed independently by each agent, then synthesized. A 1000-line contract = 5 chunks × 4 agents = 20 API calls minimum.

### 3. Batch Processing
The batch scanner processes multiple contracts in parallel, with configurable concurrency. Audit firms processing 10+ contracts daily easily hit 5M+ tokens.

### 4. Interactive Security Q&A
The built-in AI assistant answers security questions with deep context, consuming tokens on every interaction.

## Token Consumption Estimates

| Scenario | Contracts | Chunks | Agents | Tokens/Day |
|----------|-----------|--------|--------|------------|
| Single audit | 1 | 2-3 | 4 | ~50K |
| Daily monitoring | 5 | 10-15 | 4 | ~300K |
| Audit firm workload | 10+ | 30+ | 4 | ~1.5M |
| Full pipeline (batch + QA) | 20+ | 60+ | 4+chat | ~5M+ |

## 🚀 Quick Start

### Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add your MiMo API key
uvicorn app.main:app --reload --port 8000
```

### Frontend (Static)

```bash
cd frontend
# Serve with any static server
python -m http.server 3000
# Or deploy to Netlify/Vercel
```

### Environment Variables

```env
MIMO_API_KEY=your_xiaomi_mimo_api_key
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.5-pro
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Single contract analysis |
| POST | `/api/batch-analyze` | Batch contract scanning |
| POST | `/api/upload` | Upload .sol file |
| POST | `/api/chat` | Security Q&A |
| GET | `/api/stats` | Token usage statistics |
| GET | `/api/stats/history` | Usage history |
| GET | `/api/stats/trend` | Daily usage trend |

## 🛠️ Tech Stack

- **AI Model**: Xiaomi MiMo v2.5 Pro (1.6B reasoning model)
- **Backend**: Python, FastAPI, OpenAI SDK
- **Frontend**: Vanilla JS, CSS3, Dark Theme
- **API Protocol**: OpenAI-compatible (works with Claude Code, Cursor, etc.)
- **Token Management**: Real-time tracking, budget enforcement, per-agent breakdown

## 📊 Daily Token Budget

ChainSentinel is designed to consume **5-10 million tokens daily** through:

1. **Continuous contract monitoring** — watching for new deployments on-chain
2. **Batch audit processing** — parallel analysis of multiple contracts
3. **Deep analysis pipeline** — 4 agents × multiple code chunks
4. **Interactive Q&A** — developer security consultations
5. **Report generation** — professional PDF-ready audit reports

## License

MIT
