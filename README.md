# InteropSync — SWS ↔ Department Interoperability Layer

> **PanIIT AI for Bharat Hackathon — Theme 2**
> Two-way propagation middleware between Karnataka's Single Window System and 40+ legacy department systems, with **Azure GPT-4.1** grounded conflict resolution. Sits as a decision-support overlay — neither SWS nor any department system is modified.

---

## What it solves

Karnataka's business registrations live in two competing places:
- **Single Window System (SWS)** — the forward-looking front door for new businesses
- **40+ legacy department systems** — Shop Establishment, Factories, Labour, KSPCB, BESCOM, etc., still authoritative for businesses already on their books

A change made on either side does not propagate to the other → **split-brain state**. Big-bang migration is unrealistic (the GST rollout is the cautionary tale).

InteropSync is a non-invasive middleware that:
- **Propagates** service requests in both directions, joined by **UBID** from Theme 1
- **Translates** between heterogeneous schemas (5 dept-specific mappings + value transforms)
- **Detects + resolves** conflicts when both sides update the same UBID concurrently
- **Audits** every propagation with payload hash, source schema, target schema, and reviewer decision

**Brief non-negotiables met:** source systems unmodified · UBID is the only join key · idempotent + at-least-once · synthetic data only · no hosted-LLM on raw PII (synthetic demo only; on-prem path documented).

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env.local`:

```env
# Required for AI features (briefing + conflict recommendation + sync narration)
AZURE_OPENAI_API_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2025-01-01-preview

# Optional fallback if Azure not available
# OPENAI_API_KEY=sk-...
```

> **Without API keys:** the app runs fully — every AI block falls back to deterministic templates. All sync, conflict detection, and audit work offline.

```bash
uvicorn main:app --port 8001 --reload
```

Backend on **http://127.0.0.1:8001** · OpenAPI docs at `/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend on **http://localhost:5173** · proxies `/api` → port 8001

### Demo data

Already seeded in `backend/interop.db`:
- 10 SWS applications, 30 department records (3 depts each)
- 27 sync events (mixed SWS→Dept and Dept→SWS)
- 6 deliberately-seeded conflicts (2 critical, 4 warnings)
- 5 schema mappings (labour, kspcb, commercial_tax, factories, fire_safety)

To re-seed:

```bash
cd backend && source .venv/bin/activate
python ../demo/seed_demo.py
```

---

## Key features

| Feature | Where |
|---------|-------|
| **AI Morning Briefing** (Azure GPT-4.1) | `/` Dashboard — top card |
| **AI Conflict Resolution Recommendation** (Azure GPT-4.1) | `/conflicts` — per-conflict card |
| **Retry Failed Syncs** with exponential backoff | `/` Dashboard — toolbar button |
| **Bidirectional sync** (SWS → Dept · Dept → SWS) | `/` Dashboard "Sync All" |
| **Idempotency** via SHA-256 payload hash | Every sync event |
| **Conflict detection** (rapidfuzz fuzzy match + status comparison) | Backend `conflict_detector.py` |
| **Schema translation** for 5 departments | Backend `schema_translator.py` |
| **5-state conflict workflow** (UNRESOLVED → SWS_WINS / DEPT_WINS / MERGED / MANUAL) | `/conflicts` |
| **Audit trail** with source + translated payload + payload hash | `/sync-events` |

---

## API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Service health |
| GET | `/api/dashboard/overview` | KPIs + AI briefing |
| GET | `/api/applications/` | List SWS applications |
| POST | `/api/sync/sws-to-dept` | Trigger SWS→Dept propagation |
| POST | `/api/sync/dept-to-sws` | Trigger Dept→SWS propagation |
| POST | `/api/sync/retry-failed` | **Retry FAILED syncs** with exponential backoff |
| GET | `/api/sync/events` | Audit-trail event list |
| GET | `/api/sync/events/{id}/explain-llm` | **AI audit summary** for a sync event |
| GET | `/api/conflicts/` | List conflicts (filterable) |
| GET | `/api/conflicts/stats` | Conflict severity + resolution rollup |
| GET | `/api/conflicts/{id}/recommend-llm` | **AI resolution recommendation** |
| PUT | `/api/conflicts/{id}/resolve` | Reviewer confirms strategy + value |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + SQLAlchemy 2 + SQLite (PostgreSQL-portable) |
| Sync engine | rapidfuzz fuzzy match + SHA-256 idempotency hash |
| Frontend | React 18 + Vite + TypeScript + Tailwind + lucide-react |
| AI / LLM | Azure OpenAI GPT-4.1 (enterprise) — fully optional |
| Data | 10 synthetic SWS apps · 30 dept records · 6 seeded conflicts |

---

## Architecture

```
backend/
├── main.py                            FastAPI entry + 5 routers
├── app/
│   ├── database.py                    SQLAlchemy session
│   ├── models.py                      SWSApplication · DepartmentRecord · SyncEvent · ConflictRecord · SchemaMapping
│   ├── routers/
│   │   ├── applications.py            SWS app list + detail
│   │   ├── sync.py                    Bidirectional sync + AI explain + retry
│   │   ├── conflicts.py               List · resolve · AI recommend
│   │   └── dashboard.py               KPI rollup + AI briefing
│   └── services/
│       ├── sync_engine.py             Two-way propagation with idempotency hash
│       ├── schema_translator.py       Bidirectional field maps for 5 depts
│       ├── conflict_detector.py       Fuzzy + exact field comparison
│       └── llm_narration.py           Azure GPT-4.1 grounded narration
└── data/llm_cache/                    Cached LLM responses

frontend/
├── src/
│   ├── App.tsx                        Sticky nav · 4 routes · live pill
│   ├── api.ts                         Typed client (sync · conflicts · dashboard · AI)
│   └── pages/
│       ├── SyncDashboard.tsx          AI briefing + KPIs + Sync All / Retry buttons
│       ├── AuditTrail.tsx             Filterable sync-event log
│       └── ConflictResolution.tsx     Conflicts with AI Recommendation cards
```

---

## How AI is used (Azure GPT-4.1)

All AI outputs are **grounded** — GPT-4.1 only describes pre-computed sync events, conflict scores, and timestamps. Never invents UBIDs, business names, or dates. Responses cached to `data/llm_cache/` after first call → demo never breaks if network is down.

| Use case | What it does |
|----------|--------------|
| **Dashboard briefing** | 3-sentence summary: sync state + conflict + retry queue + recommended action |
| **Conflict recommendation** | Per-conflict analysis: states the disagreement (with timestamps), recommends ONE strategy (SWS_WINS / DEPT_WINS / MERGE / MANUAL), justifies in one phrase |
| **Sync audit narration** | Per-event one-liner: which fields changed, source → target, success / retry / conflict |
| **Schema mapping suggestion** | (Round 2) When onboarding a new department, suggests which dept field maps to each SWS canonical field |

**Production note:** per the brief's non-negotiables, hosted-LLM on raw PII is not permitted. This implementation operates on synthetic data only. The `lib/llm_narration.py` interface is model-agnostic — production swaps Azure for on-prem inference (Llama-3 / Mistral) by changing the URL + auth header. No application code changes.

---

## Methodology — Direction 1 (SWS → Departments)

```
1. Fetch SWS app by UBID
2. For each target dept (filtered by mapping):
   a. Translate SWS schema → dept schema (field rename + value transform)
   b. Compute SHA-256 payload hash
   c. Check idempotency (skip if last sync's hash == new hash)
   d. Detect conflicts: compare existing dept record fields vs incoming
      - Fuzzy match (rapidfuzz token_sort_ratio) for name/address (≥80% = match)
      - Exact match for status (any diff = critical)
   e. If conflicts exist: SyncEvent.status = CONFLICT, ConflictRecords created, no write
   f. If no conflicts: write to dept record, SyncEvent.status = COMPLETED
3. Audit trail: every step persisted (source schema, translated schema, payload hash, status, timestamps)
```

## Methodology — Direction 2 (Departments → SWS)

```
1. Poll department records (Round 2: Kafka topic per dept system + DLQ)
2. For each dept record with a UBID:
   a. Find matching SWS app
   b. Translate dept schema → SWS schema (reverse mapping)
   c. Idempotency check via payload hash
   d. Same conflict detection + resolution flow as Direction 1
3. Same audit trail
```

## Methodology — Conflict Resolution

```
Severity classification:
- CRITICAL: status fields disagree (any diff)
- WARNING:  name / address differ above similarity threshold (rapidfuzz < 80%)
- INFO:     pincode mismatch only

Resolution strategies (reviewer chooses, AI recommends):
- SWS_WINS:   forward-looking authority overrides
- DEPT_WINS:  legacy authoritative for existing record
- MERGED:     reviewer composes a hybrid value (rare)
- MANUAL:     reviewer enters a fresh value with justification

Every resolution: ResolvedValue + ResolverNotes + ResolvedAt persisted (append-only audit).
```

---

## Model & architecture choices (and why)

| Choice | Reason |
|--------|--------|
| **rapidfuzz fuzzy match** instead of full Splink | Token-sort ratio handles name reordering + abbreviations; runs in <1ms per pair; auditable (single similarity score per field). Splink is overkill for pairwise field comparison. |
| **SHA-256 payload hash** for idempotency | Standard at-least-once delivery primitive. If the same payload arrives twice, the second is a no-op. Hash is stored on every SyncEvent. |
| **Polling-based discovery** for v1 (Round 2 = Kafka) | Brief allows polling / snapshot diff for systems that don't emit events. Production swaps to Kafka topic per source-system without changing the sync engine. |
| **Two-tier conflict detection** (fuzzy + exact) | Status fields demand exact (legal disagreement); name/address tolerate noise (typos, formatting). Two-tier minimises false positives. |
| **Azure OpenAI GPT-4.1 for narration only** | LLMs hallucinate. We compute every score / timestamp / strategy, then ask GPT-4.1 only to **describe** them. Reviewer decides. |
| **No source-system writes outside the layer** | Brief non-negotiable. We expose `/sync/*` endpoints that the layer calls; never modify SWS or dept schemas. |

---

## Risks & mitigation

| Risk | Mitigation |
|------|-----------|
| **Lost update under concurrent writes** | SHA-256 idempotency hash + optimistic concurrency on SyncEvent.status. Round 2: per-UBID lock or conflict-aware queue. |
| **Schema drift in a department system** | SchemaMapping table is the single source of truth · onboarding a new dept = adding rows, no code change · AI mapping suggestion in Round 2. |
| **Legacy systems with no event stream** | Polling + snapshot diff (rapidfuzz comparison detects what changed) · Round 2 wraps each source in a Kafka adapter. |
| **Wrong auto-merge** (false positive resolution) | Conflicts NEVER auto-resolve · reviewer always confirms · all resolutions reversible (append-only audit). |
| **Hosted-LLM on PII forbidden** | Synthetic-only in repo · `llm_narration.py` interface is endpoint-swappable (one config change → on-prem Llama-3). |
| **Failed sync drops on the floor** | New `/sync/retry-failed` endpoint walks FAILED queue with exponential backoff (2s → 4s → 8s … capped) · attempt_count persisted per event · max-attempts before giving up to manual queue. |
| **Audit gap** | Every sync persists source_schema + translated_schema + payload_hash + status. Every conflict + resolution is a row. The audit-trail page is the system of record. |

---

## Implementation roadmap (Round 2 sandbox)

**Phase 1 — Real source-system adapters (weeks 1–4)**
- Wrap one real dept (start with Labour) in a Kafka source-connector
- Outbound webhook from SWS → InteropSync ingestion endpoint
- Real PostgreSQL backing store (SQLite is dev only)

**Phase 2 — Multi-dept pilot (weeks 5–8)**
- Onboard KSPCB and Factories alongside Labour
- 1,000 daily syncs, ~50 conflicts/week
- Reviewer team clears conflicts using AI recommendation; precision/recall measured

**Phase 3 — Snapshot diffing for non-event-emitting depts (weeks 9–12)**
- Daily snapshot pull from depts that don't emit events
- Field-level diff detection (no full re-sync)
- Mark only changed fields for translation + propagation

**Phase 4 — Production hardening (post-pilot)**
- On-prem Llama-3 swap (per non-negotiable)
- KAU compliance audit-export
- Reviewer SSO via eAuth · per-action signing
- Per-UBID rate-limit + dead-letter queue for stuck syncs

---

## Production optimisations (deferred for demo, planned for Round 2)

This is a hackathon demo on a single laptop with SQLite. Real-world Karnataka deployment at 40+ source systems, 1M+ syncs/day needs:

### Performance & scale

| Concern | Demo today | Production |
|---------|-----------|-----------|
| **Database** | SQLite (~80 KB) | PostgreSQL on managed RDS · partitioned by source_system |
| **Indexes** | Defaults only | Composite: `(direction, status, initiated_at desc)`, `(ubid, direction)`, partial on `status='FAILED'` for fast retry-queue scan |
| **Sync runtime** | Synchronous in-process | Celery workers + Redis broker · per-source-system queue isolation |
| **Polling for non-event depts** | Full record fetch | Snapshot diffing — only changed fields enter the sync engine |

### Caching

| Layer | Demo | Production |
|-------|------|-----------|
| **AI narration** | File cache (`data/llm_cache/*.txt`) | Redis with 24-hour TTL keyed by SHA256 of payload |
| **Dashboard rollup** | SQL count() per request | Redis 60-second TTL · invalidated on sync completion |
| **Schema mappings** | DB query per sync | In-memory LRU cache · refreshed on mapping-table change event |

### Concurrency & throughput

- **Per-UBID lock** in Redis to prevent two simultaneous updates from interleaving
- **Idempotent retry** with exponential backoff (already in v1) · max 5 attempts → DLQ
- **Optimistic locking** on SyncEvent.status (version column) · no silent overwrites
- **Kafka source connectors** per dept system · each consumer is independently scalable

### Observability

- **OpenTelemetry traces** on every sync — one trace spans receive → translate → conflict-detect → write → ack
- **Prometheus metrics**: `sync.duration`, `sync.conflict_rate`, `retry.attempt_count`, `ai.cache_hit_ratio`
- **Grafana dashboard** for KCI ops · per-dept SLA tracking · weekly conflict-resolution-time report

### Security

- **No hosted-LLM on raw PII** in production · `llm_narration.py` is endpoint-swappable
- **Reviewer signing** · every confirm/reject signed with reviewer ID + timestamp + IP (KAU compliance)
- **Encryption at rest** · PG TDE + KMS-managed keys for fields with PAN/GSTIN

### Cost estimate (Round 2 sandbox, 1M syncs/day)

- 1 × t3.large API VM + 1 × Redis + 1 × PG (db.t3.medium) + Kafka cluster: **~₹80K/month**
- Azure OpenAI calls (cached, ~10K/day): **~₹2K/month**
- Total infrastructure: **~₹82K/month** for the 1M-sync sandbox · scales linearly to ₹4-5 lakh/month at full scale (40 source systems, 10M+ syncs/day).

---

## Submission

- **Hackathon:** PanIIT AI for Bharat
- **Theme:** 2 — Two-Way Interoperability between SWS and Department Systems (Karnataka Commerce & Industries)
- **Team:** Sridhar Suresh · Sruthi Krishnakumar
