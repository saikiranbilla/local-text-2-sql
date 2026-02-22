# Quill — Local-First Text-to-SQL BI Agent

> Ask questions about your data in plain English. Get SQL, results, and insight — all running on your machine.

![MIT License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)
![Local First](https://img.shields.io/badge/data-local--first-orange?style=flat-square)
![DuckDB](https://img.shields.io/badge/engine-DuckDB-yellow?style=flat-square)

![Quill Demo](demo.gif)

---

## What is Quill?

Quill is a **compound AI agent** that lets you query any CSV or database using natural language. It runs entirely on your machine — no cloud warehouse, no data transmitted to third parties, no API cost per query. You own your data.

Upload a CSV. Type a question. Get results in seconds.

User  → "Show me the top 10 customers by revenue."
Quill → Resolves schema → Generates SQL → Executes → Returns table + chart + insight
User  → "Now filter those by customers in Germany."
Quill → Resolves context from history → Generates new self-contained SQL
```

---

## ✨ Features

- **Privacy-First & Fully Local**: No cloud warehouses. Your data never leaves your machine. Queries run securely via an in-process DuckDB engine.
- **Gorgeous Visualizations**: Automatically visualizes your SQL results using dynamic, theme-aware bar, line, and doughnut charts powered by Chart.js.
- **Light & Dark Mode UI**: A beautifully crafted, modern interface that seamlessly toggles between a sleek dark mode and a high-contrast, projector-safe light mode.
- **Compound AI Pipeline**: Multi-agent architecture (Relevance Gate → Semantic Resolver → SQL Generator → Critic) ensures query accuracy, hallucination prevention, and self-correction.
- **Conversational Memory**: Chat naturally with your data. Ask contextual follow-up questions and Quill understands coreferences instantly.
- **Ultra-Fast Execution**: Achieves ~20-50ms data query latency by leveraging local DuckDB and intelligent LLM prompt caching.

---

## Design Trade-offs: Why Not Just Use a Cloud BI Platform?

| Dimension | Quill (Local-First) | Cloud BI (e.g., Databricks AI/BI Genie) |
|---|---|---|
| **Data Privacy** | ✅ Stays on your machine | ❌ Data uploaded to cloud warehouse |
| **Cost** | ✅ Zero egress / query cost | ❌ Per-query compute billing |
| **Latency** | ✅ In-process DuckDB (~20–50ms) | ⚠️ Network roundtrips + cluster spin-up |
| **SQL Dialect** | DuckDB (OLAP-optimized) | Spark SQL / proprietary |
| **Setup** | `pip install` + run | Cloud account, IAM, cluster config |
| **Customization** | Full control over agents | Black-box vendor implementation |

Quill is intentionally scoped: it solves the **80% use case** (CSV analytics, local databases, privacy-sensitive data) that cloud BI platforms dramatically overprice.

---

## Architecture: The Compound AI Pipeline

Quill is not a single LLM call. It's a **four-stage agent pipeline**, where each stage has a specific, verifiable responsibility.

```
User Question
     │
     ▼
┌─────────────────────┐
│  1. Relevance Gate  │  Blocks off-topic questions immediately.
└──────────┬──────────┘
           │
     ▼
┌─────────────────────┐
│ 2. Semantic Resolver│  Hybrid TF-IDF + fuzzy match → prunes schema
└──────────┬──────────┘  to only relevant tables/columns.
           │
     ▼
┌─────────────────────┐
│ 3. SQL Generator    │  Claude Haiku (or Qwen2.5) → DuckDB SQL.
│  (with Caching)     │  Prompt cache on schema = ~90% latency drop.
└──────────┬──────────┘  Coreference resolution for follow-up Qs.
           │
     ▼
┌─────────────────────┐
│ 4. Critic Agent     │  Executes SQL. On failure, self-corrects
│  (Retry Loop)       │  with error + history. Up to 3 attempts.
└──────────┬──────────┘
           │
     ▼
  Results streamed via SSE → Chart + Table + LLM Insight Summary
```

### Key Engineering Decisions

**Semantic Resolver prevents hallucination.** The most common failure in Text-to-SQL is the LLM inventing column names that don't exist. The resolver narrows the schema context before the SQL Generator ever runs — drastically reducing the search space and grounding the model in real column names.

**Anthropic Prompt Caching.** The database schema is injected into every LLM call. For large schemas, this is expensive. Quill uses Anthropic's `cache_control: ephemeral` on the system prompt block, which caches the schema tokens server-side. On subsequent calls, those tokens are never re-processed — reducing latency by up to 90% and cutting costs by up to 75%.

**Critic Agent = Determinism over Probability.** LLMs produce probabilistic outputs. SQL execution is deterministic — it either works or it doesn't. The Critic Agent bridges this gap: if a query fails, it receives the original question, the broken SQL, and the exact error message, then generates a corrected query. This loop runs up to 3 times before surfacing an error to the user.

**Conversational Memory.** The frontend tracks `chatHistory` and sends it with every request. The SQL Generator's system prompt has a strict coreference resolution section: it is instructed to resolve pronouns ("those", "them") by inspecting prior queries rather than treating the follow-up as a fresh, unrelated question.

---

## Project Structure

```
local-text-2-sql/
│
├── agents/
│   ├── generator.py      # SQL Generator Agent (LLM → SQL)
│   ├── critic.py         # Critic Agent (retry loop)
│   └── resolver.py       # Semantic Resolver (schema pruning)
│
├── api/
│   └── routes.py         # FastAPI endpoints (SSE streaming)
│
├── core/
│   ├── engine.py         # DuckDB wrapper
│   ├── llm_client.py     # Unified LLM client (Claude / Qwen)
│   ├── orchestrator.py   # Agent pipeline coordinator
│   └── utils.py          # sanitize_identifier, clean_sql
│
├── prompts/
│   └── templates.py      # System prompts for all agents
│
├── ui/
│   └── index.html        # Frontend (Vanilla JS, Tailwind, Chart.js)
│
├── docs/
│   └── index.html        # GitHub Pages landing page
│
├── tests/                # pytest suite
├── data/                 # CSV files loaded into DuckDB
├── main.py               # FastAPI entrypoint
└── requirements.txt
```

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/saikiranbilla/local-text-2-sql.git
cd local-text-2-sql
```

### 2. Create a virtual environment

```bash
python -m venv env

# macOS / Linux
source env/bin/activate

# Windows
.\env\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your LLM

**Option A — Claude Haiku (Recommended)**

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Option B — Qwen2.5 (Fully Local, no API key)**

Ensure [Ollama](https://ollama.com) is running with the `qwen2.5` model pulled:

```bash
ollama pull qwen2.5
```

### 5. Start the server

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser.

### 6. Upload a CSV and start querying

1. Click the file upload area in the sidebar to add a `.csv` dataset.
2. Select your newly uploaded dataset from the active table dropdown.
3. Type a natural language question in the chat input.
4. Enjoy your fast, local, and visual results!

---

## 🎨 UI Showcase

Quill's frontend is built from scratch avoiding generic framework components, giving it a premium, glassmorphic aesthetic. It features an advanced chart generation heuristic that dynamically selects the best way to represent your returned data rows!

---

## Running Tests

```bash
pytest tests/ -v
```

---

## License

MIT — see [LICENSE](LICENSE).

---

**Built by [Sai Kiran Billa](https://www.linkedin.com/in/saikiranbilla) · AI Software Engineer**