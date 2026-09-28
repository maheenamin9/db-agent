# DB Agent

Connect a CSV, a Google Sheet, a Postgres database, or a MySQL database; describe
what the data means in plain English; then ask questions about it in plain English
and get back an answer, the SQL that produced it, a table, and a chart — regardless
of which of those sources the data actually came from.

## The idea

Every source is different, but once you point the agent at one, it ends up in the
same place: a local [DuckDB](https://duckdb.org/) file. That's the one thing the
question-answering agent ever has to know how to query, so it doesn't matter
whether a table came from a live Postgres database or a spreadsheet someone
uploaded five minutes ago — from the agent's point of view, there's no difference.

```
CSV / Excel ──┐
Google Sheets ─┼──►  connectors  ──►  DuckDB  ◄──  LangGraph agent  ──►  answer / SQL / rows
Postgres ──────┤        (unify)      (the only         (asks Ollama,
MySQL ─────────┘                    thing queried)      queries Qdrant)

                    Semantics (your descriptions)
                            │
                            ▼
                    Qdrant (embedded, searchable)
```

Postgres and MySQL are queried live only for browsing tables and for the one-time
import into DuckDB; after that, everything — including re-running the same
question twice — only ever touches the local DuckDB copy. Files and spreadsheets
skip the "live" step entirely, since there's nothing to query until they're loaded.

## What it's built from

**Backend**: FastAPI + [uv](https://docs.astral.sh/uv/), DuckDB, Qdrant, [LangGraph](https://langchain-ai.github.io/langgraph/), Ollama.
**Frontend**: Next.js (App Router), TypeScript, Tailwind, [Recharts](https://recharts.org/).
**Infra**: Docker Compose (backend, frontend, Qdrant, a seeded Postgres, a seeded MySQL).

### Models

Two backends are supported, selected by `LLM_PROVIDER` (default `ollama`):

- **`ollama`** — runs models locally (or on any reachable host). Good for privacy
  and offline use; latency depends on the machine running Ollama.
- **`groq`** — routes chat calls to [Groq's API](https://console.groq.com/). Much
  faster inference than a local GPU for most models; requires `GROQ_API_KEY` to be
  set in `.env` and Groq-compatible model ids in `SQL_MODEL`/`DESCRIBE_MODEL` (e.g.
  `llama-3.3-70b-versatile`).

Embeddings always stay on Ollama regardless of `LLM_PROVIDER` — Groq has no
embeddings API, so `EMBED_MODEL` and `OLLAMA_HOST` must always be configured.

Three separate models, each picked for what it actually needs to do — there's no
single "the model" here:

| Purpose | Setting | Default (Ollama) | Groq equivalent | Why this one |
|---|---|---|---|---|
| Embeddings (semantic search) | `EMBED_MODEL` | `nomic-embed-text` | *(always Ollama)* | Small (137M params), purpose-built for embeddings rather than chat, 768-dimensional output |
| SQL generation, repair, and answer summarization | `SQL_MODEL` | `qwen3:30b` | `llama-3.3-70b-versatile` | Runs 1-3+ times per question (initial attempt plus up to 2 repairs, plus the final answer), so it needs to be capable enough to get DuckDB SQL right |
| One-off table/column description generation | `DESCRIBE_MODEL` | `qwen3:8b` | `llama-3.1-8b-instant` | A simpler, less latency-sensitive job (one short sentence per field), so a faster/smaller model is the better trade-off |

**A real caveat, not a footnote**: with Ollama, latency for a single question has
been observed anywhere from under a minute to around fifteen minutes, depending on
the model and apparent load on wherever Ollama is running. Groq is significantly
faster in practice. The UI reflects variable latency with a live elapsed-time
counter instead of a plain spinner, and there's no artificial timeout on the
request — it waits as long as it takes.

## How a question actually gets answered

The agent is a [LangGraph](https://langchain-ai.github.io/langgraph/) state
machine (`backend/app/agent/graph.py`), not a single prompt:

```
question ──► guard ──► retrieve ──► generate_sql ──► validate ──► execute ──► answer ──► done
                                                          ▲            │
                                                          └── repair ◄─┘
```

`guard` can skip straight to `answer` (a blocked question). `validate` and
`execute` can each fail into `repair`, which loops back to `validate` — but only
while `repair_count < 2`; past that, a failure also goes straight to `answer`,
which reports it instead of trying again. The numbered steps below are the exact
logic; the diagram above is just the gist.

1. **guard** — *technique: leading-verb regex heuristic (no LLM call).* Strips
   common filler phrases ("please", "can you", …) and checks whether the first real
   word is a known destructive verb (`delete`, `update`, `drop`, …). Only flags
   commands that *lead* with that verb, so questions like "Which orders were deleted
   last month?" pass through unblocked. Latency optimization only — that's step 4.
2. **retrieve** — *technique: dense vector search (cosine similarity) over Qdrant.*
   Embeds the question with the embedding model and returns the top-`RETRIEVAL_TOP_K`
   (default 8) chunks — one chunk per table, column, or relationship — by cosine
   similarity. See [Semantic search](#semantic-search-what-gets-embedded) below.
3. **generate_sql** — *technique: few-shot prompting with retrieved schema context.*
   Builds a prompt from the question, the retrieved chunks, and two hard-coded
   few-shot examples, then asks the SQL model to emit DuckDB SQL wrapped in a
   fenced code block. `extract_sql` pulls the first such block from the response.
4. **validate** — *technique: AST allowlist via `sqlglot` (not a keyword blocklist).*
   Parses the SQL and checks that exactly one statement exists and that its top-level
   node is a `Select`. Because CTEs (`WITH … SELECT`) parse as `Select` nodes too,
   no separate case is needed. This rejects anything that isn't a `SELECT` —
   including `ATTACH`, `COPY`, `PRAGMA`, `SET`, and other statements a keyword regex
   would miss — and caps or adds a `LIMIT` clause.
5. **execute** — *technique: DuckDB read-only transaction.* Runs the validated SQL
   inside a read-only connection so even a statement that somehow slipped past
   validation still cannot write anything. Errors are caught and returned as `error`
   for the repair loop.
6. **repair** — *technique: error-grounded re-prompting with the failed SQL.*
   Feeds the original question, retrieved context, the failed SQL, and the exact
   error message back to the SQL model and asks it to produce a corrected query.
   Runs at most twice (`MAX_REPAIR_RETRIES`) before the loop gives up.
7. **answer** — *technique: grounded summarization (success) or fixed template
   (failure).* On success, prompts the model with the *real, executed* SQL and the
   result rows so it cannot claim a write happened when only a read did. On failure,
   returns a fixed message string with no further LLM call, ensuring a broken loop
   can always explain itself.

### Semantic search: what gets embedded

The building block is one *chunk* per fact, not one chunk per table
(`backend/app/indexing/chunks.py`):

- one chunk per **model** ("Table orders: customer purchases.")
- one chunk per **column** ("Table orders, column status (VARCHAR): the order's current status.") — the table name is repeated in the sentence, not just attached as metadata, because a search can return a column's chunk on its own with no guarantee the table's chunk comes back alongside it
- one chunk per **relationship** ("orders.customer_id references customers.id (many_to_one).")

Deploying embeds every chunk and upserts them into a single Qdrant collection
(wipe-and-rebuild each time — no incremental updates). Answering a question embeds
the question the same way and does a cosine-similarity search for the top `RETRIEVAL_TOP_K`
(default 8) chunks, which become the schema context handed to the SQL model.

## Project layout

```
backend/
  app/
    connectors/     # CSV/Excel, Google Sheets, Postgres, MySQL — one shared interface
    duckdb_helper.py
    agent/          # guard, retrieve/generate_sql/validate/execute/repair/answer, graph
    semantics/      # the Model/Column/Relationship schema, YAML store, description generation
    indexing/       # chunking, embeddings, Qdrant client
    routers/        # one FastAPI router per resource
  tests/
  data/             # warehouse.duckdb, semantics.yaml — real, persistent app state
frontend/
  app/              # one page per step: sources, tables, relationships, semantics, deploy, ask
  components/
  lib/api.ts        # the only place that talks to the backend
seed/               # demo schema + data for the Postgres/MySQL containers
docker-compose.yml
```

## Running it

### Prerequisites

- [uv](https://docs.astral.sh/uv/) and Node.js 20+, if running outside Docker
- Docker, for Qdrant/Postgres/MySQL (and optionally the backend/frontend too)
- [Ollama](https://ollama.com/), reachable at whatever `OLLAMA_HOST` you configure, with `nomic-embed-text`, `qwen3:30b`, and `qwen3:8b` pulled (or your own choice of models — see [Models](#models))

Copy `.env.example` to `.env` and adjust at least `OLLAMA_HOST`.

### Local (recommended while developing — hot reload, no rebuilds)

Start the infra Qdrant/Postgres/MySQL need in Docker, run the app itself natively:

```bash
docker compose up -d qdrant postgres mysql

cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000

cd frontend
npm install
npm run dev
```

Frontend: http://localhost:3000 — Backend: http://localhost:8000/docs

### Full Docker

```bash
docker compose up -d --build
```

This builds and starts everything: backend (8000), frontend (3000), Qdrant (6333),
Postgres (5432→5433 on the host, since 5432 is often already taken locally), MySQL
(3306). Rebuild (`--build`) after any backend or frontend code change — the images
copy code in at build time, they don't mount it live.

To wipe the seeded Postgres/MySQL data and start over: `docker compose down -v`
(the seed scripts only run against an empty volume).

### Tests

```bash
cd backend
uv run pytest                       # everything reachable right now
uv run pytest -m "not integration"  # no Ollama/Postgres/MySQL required
uv run pytest -m integration        # real Ollama + real seeded databases; skips cleanly if unreachable
```

Most of the suite runs against fakes and an in-memory DuckDB. A smaller set of
tests marked `integration` exercise the real pipeline end to end — real Ollama,
real Qdrant, real seeded Postgres — and are the slow ones (a single real
SQL-generation call has taken anywhere from seconds to minutes).

## Using it

The frontend is one step per stage, in order:

1. **Sources** — connect a Postgres/MySQL database (read-only credentials only —
   the agent should never hold write access), upload a CSV/Excel file, or load a
   Google Sheet by URL. Files and sheets land in DuckDB immediately; databases are
   browsed live first.
2. **Tables** — pick which of a connected database's tables to pull into DuckDB,
   and which of everything already in DuckDB counts as "part of the project" (as
   distinct from being physically deleted, which is also possible from here).
3. **Relationships** — accept heuristic foreign-key suggestions (matched by column
   naming convention and type, not a live database constraint) or add/edit/delete
   them by hand.
4. **Semantics** — write a short description of each table and column (or
   generate a first draft with the describe model and edit it), and see the
   relationships from the step before.
5. **Deploy** — embed everything above and index it into Qdrant.
6. **Ask** — ask a question in plain English; get an answer, the SQL that ran, a
   paginated table of the result, and a chart (Bar/Line/Pie/Scatter, picked from
   the columns actually returned — no extra request needed to render it).

## API reference

All routes are under the backend's root (e.g. `http://localhost:8000`).

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `POST /sources` | Connect a Postgres/MySQL database |
| `GET /sources` | List connected databases |
| `GET /sources/{id}/tables` | Browse a connected database's tables live |
| `POST /sources/{id}/import` | Copy selected tables into DuckDB |
| `POST /sources/upload` | Upload a CSV/XLSX file |
| `POST /sources/gsheets` | Load a Google Sheet by URL or id |
| `GET /tables` | Every table currently in DuckDB |
| `GET /tables/selection` | Which tables are currently in scope |
| `POST /tables/select` | Set which tables are in scope |
| `DELETE /tables/{name}` | Drop a table, and clean up anything describing it |
| `GET` / `PUT /semantics` | Read/write the models, columns, and relationships |
| `POST /semantics/sync` | Add any DuckDB table/column not yet described (never overwrites) |
| `POST /semantics/generate/{table}` | Draft descriptions for a table's still-empty fields |
| `GET /relationships` | List saved relationships |
| `POST /relationships/suggest` | Heuristic foreign-key candidates (not persisted) |
| `POST` / `PUT` / `DELETE /relationships[/{id}]` | Create/edit/delete a relationship |
| `POST /deploy` | Embed semantics and index into Qdrant |
| `POST /ask` | Ask a question; returns `{answer, sql, rows, row_count, error}` |

Full request/response shapes: `http://localhost:8000/docs` (FastAPI's interactive
docs) once the backend is running.

## Known limitations

- **Latency is real and variable.** A single question can take anywhere from
  seconds to minutes, depending on the model and Ollama's load. There's no
  timeout on the request.
- **The input guard is a fast filter, not a security boundary.** It only catches
  a destructive verb leading the sentence. The SQL validator (step 4 above) is
  what actually enforces read-only access, and it applies regardless of what the
  guard does or doesn't catch.
- **DuckDB is a snapshot.** Once a table is imported, it doesn't update when the
  original source changes — re-import to refresh it.
- **Relationships are heuristic**, matched by column-naming convention and type,
  not read from the source database's real foreign-key constraints.
