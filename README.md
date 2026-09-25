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

Three separate local models, each picked for what it actually needs to do — there's
no single "the model" here:

| Purpose | Setting | Default | Why this one |
|---|---|---|---|
| Embeddings (semantic search) | `EMBED_MODEL` | `nomic-embed-text` | Small (137M params), purpose-built for embeddings rather than chat, 768-dimensional output |
| SQL generation, repair, and answer summarization | `SQL_MODEL` | `qwen3:30b` | Runs 1-3+ times per question (initial attempt plus up to 2 repairs, plus the final answer), so it needs to be capable enough to get DuckDB SQL right without being so large that every question takes forever |
| One-off table/column description generation | `DESCRIBE_MODEL` | `qwen3:8b` | A much simpler, less latency-sensitive job (one short sentence per field), so a faster/smaller model is the better trade-off here |

All three are reached through `OLLAMA_HOST`, which can point at a model running on
this machine or anywhere else reachable on the network — nothing here assumes
Ollama is local.

**A real caveat, not a footnote**: local-model latency for a single question has
been observed anywhere from under a minute to around fifteen minutes, depending on
the model and apparent load on wherever Ollama is running. The UI reflects this
with a live elapsed-time counter instead of a plain spinner, and there's no
artificial timeout on the request — it waits as long as it takes.

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

1. **guard** — a fast, deterministic check (no LLM call) for a question that's
   obviously asking to *change* data rather than read it ("delete the customer
   named X"). This only catches the common, directly-phrased case, and it's a
   latency optimization, not the actual safety mechanism — that's step 4.
2. **retrieve** — embeds the question and searches Qdrant for the most relevant
   pieces of your semantic description (see [Semantic search](#semantic-search-what-gets-embedded) below).
3. **generate_sql** — asks the SQL model for DuckDB SQL, given the retrieved
   context and two few-shot examples.
4. **validate** — parses the SQL with [`sqlglot`](https://github.com/tobymao/sqlglot)
   and only allows a single `SELECT` (or `WITH ... SELECT`) statement through — an
   allowlist, not a keyword blocklist, so it also rejects things a blocklist would
   miss (`ATTACH`, `COPY`, `PRAGMA`, `SET`, ...), not just the obvious `INSERT`/`UPDATE`/`DELETE`/`DROP`.
   A missing `LIMIT` gets one added; an absurdly large explicit one is rejected.
5. **execute** — runs the query inside a DuckDB read-only transaction, so even a
   statement that somehow got past validation still couldn't write anything.
6. **repair** — on failure, feeds the exact error and the failed SQL back to the
   model and tries again, up to twice (`MAX_REPAIR_RETRIES`).
7. **answer** — summarizes the result rows in plain English. On failure, this is a
   fixed message with no further LLM call, so a broken loop can't also fail to
   explain itself. Answer generation is grounded in the *real, executed* SQL, not
   just the original question — otherwise, for a question like "delete customer X"
   that gets silently converted into a lookup, the model has no way to know a
   write didn't happen and can end up claiming it did.

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
