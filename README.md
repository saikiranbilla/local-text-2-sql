# Quill — Local-First Text-to-SQL BI Agent

> Ask questions about your data in plain English. Get SQL, results, and insights — all running on your machine.

[![MIT License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://www.python.org/downloads/)
[![DuckDB](https://img.shields.io/badge/engine-DuckDB-yellow?style=flat-square)](https://duckdb.org)
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-009688?style=flat-square)](https://fastapi.tiangolo.com)

![Quill Demo](demo.gif)

---

## Table of Contents

- [What is Quill?](#what-is-quill)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Contributing](#contributing)
- [Getting Help](#getting-help)
- [License](#license)

---

## What is Quill?

Quill is a **compound AI agent** that turns natural language questions into SQL queries, executes them against your local data, and streams back results with charts and LLM-generated insights — entirely on your machine.

```
User  → "Show me the top 10 customers by revenue."
Quill → Resolves schema → Generates SQL → Executes → Returns table + chart + insight

User  → "Now filter those by customers in Germany."
Quill → Resolves context from history → Generates new self-contained SQL
```

No cloud warehouse. No data leaving your machine. No per-query billing. Upload a CSV and start querying in seconds.

---

## Features

| Feature | Description |
|---|---|
| **Natural Language Queries** | Ask questions in plain English — Quill handles schema mapping and SQL generation |
| **Multi-Agent Pipeline** | Four-stage pipeline (Relevance Gate → Semantic Resolver → SQL Generator → Critic) for accurate, self-correcting queries |
| **Conversational Memory** | Ask follow-up questions with pronoun resolution ("those customers", "that product") |
| **Auto-Visualization** | Heuristic chart selection — bar, line, stacked, horizontal — based on your data shape |
| **SSE Streaming** | Real-time step-by-step feedback as Quill thinks, generates SQL, and summarizes results |
| **CSV Upload** | Upload any CSV and immediately query it; Quill auto-detects schema and types |
| **Dark / Light Mode** | Theme-aware UI with localStorage persistence |
| **Privacy-First** | All data and query execution stay local via in-process DuckDB |
| **Prompt Caching** | Anthropic `cache_control: ephemeral` on system prompts — up to 90% latency reduction |
| **Bundled Datasets** | Ships with Northwind (11 tables) and UIUC datasets ready to query out of the box |

---

## Architecture

Quill is a **four-stage compound AI pipeline**. Each stage has a specific, verifiable job.

```
User Question
     │
     ▼
┌─────────────────────┐
│  1. Relevance Gate  │  Blocks off-topic questions using fuzzy keyword
└──────────┬──────────┘  matching against schema identifiers.
           │
           ▼
┌─────────────────────┐
│ 2. Semantic Resolver│  Hybrid TF-IDF + sentence-transformer embeddings
└──────────┬──────────┘  prune the schema to only relevant tables/columns.
           │             Sample values extracted for LLM grounding.
           ▼
┌─────────────────────┐
│ 3. SQL Generator    │  LLM generates DuckDB SQL from pruned schema.
│  (with Caching)     │  Schema tokens cached server-side via
└──────────┬──────────┘  cache_control: ephemeral. Chat history injected
           │             for coreference resolution.
           ▼
┌─────────────────────┐
│ 4. Critic Agent     │  Executes SQL. On failure, sends original question
│  (Retry Loop)       │  + broken SQL + error to LLM for correction.
└──────────┬──────────┘  Up to 3 self-correction attempts.
           │
           ▼
Results → SSE Stream → Chart + Table + AI Insight Summary
```

### Why this design?

**Semantic Resolver prevents hallucination.** The most common failure in Text-to-SQL is the LLM inventing column names that don't exist. By narrowing schema context before generation, Quill grounds the model in real identifiers only.

**Critic = determinism over probability.** SQL execution is binary — it works or it doesn't. The Critic bridges this gap: failed queries are automatically corrected using the exact error message and full failure history, with up to 3 retries before surfacing an error.

**Hybrid matching.** The resolver uses `thefuzz` for fuzzy string matching plus `sentence-transformers` (`all-MiniLM-L6-v2`) for semantic similarity. Falls back to fuzzy-only if transformers are unavailable.

**Prompt caching.** The database schema is injected into every LLM call. For large schemas this is expensive. Quill applies `cache_control: ephemeral` on the system prompt block so schema tokens are only processed once per cache window — cutting latency up to 90% and cost up to 75%.

---

## Quick Start

### Prerequisites

- Python 3.11+
- A [Keywords AI](https://keywordsai.co) account (free tier available)

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

> **Note:** Installing `sentence-transformers` will download the `all-MiniLM-L6-v2` model (~90 MB) on first run. If you skip it, Quill falls back to fuzzy-only matching.

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required — get your key at https://keywordsai.co
KEYWORDSAI_API_KEY=your_keywordsai_key_here

# Any model supported by Keywords AI
MODEL=claude-haiku-3-5
```

Keywords AI is an OpenAI-compatible proxy that routes to Claude, GPT-4, Gemini, and more through a single key. You can swap `MODEL` to any supported model without touching code.

### 5. Start the server

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser.

### 6. Start querying

Quill ships with the [Northwind dataset](data/) (11 tables — customers, orders, products, employees, and more) pre-loaded. No upload needed to get started.

Try asking:
- *"Show me total revenue by product category."*
- *"Which employees have the most orders?"*
- *"Top 5 customers by order count in Germany."*

---

## Usage

### Querying your own data

1. Click the **upload area** in the sidebar and select a `.csv` file.
2. Quill auto-detects column types, sanitizes identifiers, and loads the table into DuckDB.
3. Toggle the table on in the **Your Tables** list to include it in queries.
4. Ask a question — Quill will restrict SQL generation to only your selected tables.

### Follow-up questions

Quill maintains chat history across your session. You can ask follow-up questions with natural references:

```
"Show me the top 10 products by revenue."
"Which of those are from the Beverages category?"
"Now sort by supplier country."
```

Each follow-up receives the prior SQL and question as context for coreference resolution.

### Exporting results

Click **Export Session PDF** in the sidebar to capture the full conversation — questions, SQL, tables, and charts — as a PDF.

### Switching models

Update `MODEL` in your `.env` file and restart the server. Any model available on Keywords AI works — including Claude, GPT-4o, and Gemini variants.

---

## API Reference

All endpoints are prefixed under `/api`. Full interactive docs available at **http://localhost:8000/docs** when the server is running.

### `POST /api/query`

Runs the full pipeline and streams results as Server-Sent Events.

**Request body:**
```json
{
  "question": "Show me total revenue by country.",
  "selectedTables": ["orders", "order_details", "customers"],
  "chat_history": []
}
```

**SSE event types:**

| Event | Payload | Description |
|---|---|---|
| `thinking` | `{ "step": "..." }` | Step-by-step reasoning progress |
| `sql` | `{ "sql": "SELECT ..." }` | Generated SQL query |
| `result` | `{ "data": [...], "row_count": N, "attempts": N }` | Query results as JSON records |
| `summary` | `{ "chunk": "..." }` | Streamed AI insight token |
| `summary_done` | `{}` | End of insight stream |
| `error` | `{ "message": "..." }` | Pipeline failure |

### `GET /api/tables`

Returns all loaded tables with schema and row counts.

**Response:**
```json
{
  "tables": [
    {
      "name": "orders",
      "row_count": 830,
      "columns": [
        { "name": "orderID", "type": "INTEGER" },
        { "name": "customerID", "type": "VARCHAR" }
      ]
    }
  ]
}
```

### `POST /api/upload`

Upload a CSV file and load it into DuckDB.

**Request:** Multipart form with a `file` field containing a `.csv` file.

**Response:**
```json
{
  "success": true,
  "table_name": "my_data",
  "row_count": 1500,
  "columns": ["id", "name", "revenue"]
}
```

### `DELETE /api/tables/{table_name}`

Drop a table from DuckDB and remove the backing CSV file.

**Response:**
```json
{
  "success": true,
  "message": "Table 'my_data' deleted."
}
```

---

## Project Structure

```
local-text-2-sql/
│
├── agents/
│   ├── generator.py      # SQL Generator Agent — LLM → DuckDB SQL
│   ├── critic.py         # Critic Agent — execute + retry loop (3 attempts)
│   └── resolver.py       # Semantic Resolver — fuzzy + embedding schema pruning
│
├── api/
│   └── routes.py         # FastAPI endpoints + SSE streaming logic
│
├── core/
│   ├── engine.py         # DuckDB wrapper — load, execute, schema, relationships
│   ├── llm_client.py     # Shared AsyncAnthropic client (Keywords AI proxy)
│   ├── orchestrator.py   # Pipeline coordinator — wires all agents together
│   └── utils.py          # clean_sql(), sanitize_identifier()
│
├── prompts/
│   └── templates.py      # System prompts for generator, critic, and schema formatting
│
├── ui/
│   └── index.html        # Vanilla JS SPA — SSE rendering, Chart.js, upload, themes
│
├── docs/
│   └── index.html        # GitHub Pages landing page
│
├── tests/
│   ├── test_engine.py    # DuckDB schema + execution tests
│   ├── test_resolver.py  # Keyword extraction + fuzzy matching tests
│   └── test_utils.py     # SQL cleaning + identifier sanitization tests
│
├── data/                 # Northwind + UIUC CSV datasets (auto-loaded on startup)
├── src/                  # Data loading utilities
├── main.py               # FastAPI entrypoint — mounts routes + static UI
├── .env.example          # Environment variable template
└── requirements.txt      # Python dependencies
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use temporary directories with dummy CSVs — no external services required.

To run a specific test file:

```bash
pytest tests/test_engine.py -v
pytest tests/test_resolver.py -v
```

---

## Contributing

Contributions are welcome. To get started:

1. Fork the repository and create a feature branch.
2. Make your changes with tests where applicable.
3. Ensure `pytest tests/ -v` passes.
4. Open a pull request with a clear description of the change.

For larger changes, open an issue first to discuss the approach.

---

## Getting Help

- **Bug reports & feature requests:** [Open an issue](https://github.com/saikiranbilla/local-text-2-sql/issues)
- **Interactive API docs:** `http://localhost:8000/docs` (when server is running)
- **Keywords AI docs:** [keywordsai.co](https://keywordsai.co) — for model configuration and API key management
- **DuckDB SQL reference:** [duckdb.org/docs](https://duckdb.org/docs/sql/introduction)

---

## License

MIT — see [LICENSE](LICENSE).

---

**Built by [Sai Kiran Billa](https://www.linkedin.com/in/saikiranbilla) · AI Software Engineer**
