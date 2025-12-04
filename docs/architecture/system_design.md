# Flux v1.0 System Architecture Design
**Author**: [ARCH] – System Architect
**Phase**: 1 (Foundation)
**Status**: Ready for Specialist Review (DATA, BACKEND, SEC, QA)

## 1. Architecture Overview
Flux is an **Event-Driven, Worker-Offloaded SaaS** system optimized for:
*   **<100ms API latency**
*   **Heavy compute in async Workers**
*   **Strict row-level tenant isolation (RLS)**
*   **Deterministic analytics pipelines**

## 2. Core Components & Responsibilities

### 2.1 API Service (FastAPI)
*   **Role**: "Traffic Cop"
*   **Handles**:
    *   HTMX partial templates
    *   Auth (JWT / API keys)
    *   Lightweight business logic
    *   Dispatching jobs to Redis queues
*   **Strict Rule**: 🚫 API must never run forecasting, inventory, or scheduling computations.
*   **Performance Contract**:
    *   100ms p99 latency
    *   All expensive tasks must be enqueued to Redis

### 2.2 Message Broker (Redis + Dramatiq)
*   **Queues** (explicit contract for worker scaling):
    *   `ingest`: POS webhooks (High concurrency)
    *   `analytics`: Forecasting, Inventory, Staffing (CPU-heavy pool)
    *   `default`: UI-triggered tasks (Small pool)
*   **Retry Semantics**:
    *   3 automatic retries
    *   Exponential backoff
    *   Poison queue (`dead_letter`) for manual inspection
*   **Idempotency Contract**: Workers must be able to safely re-run tasks.

### 2.3 Worker Service (Dramatiq Workers)
*   **Executes Engines**:
    *   A: Ingestion
    *   B: Forecasting
    *   C: Inventory Optimization
    *   D: Staffing Optimization
*   **Scaling Contract**: Worker replicas auto-scale by queue depth.
*   **Isolation**: Each worker must set `SET LOCAL app.current_tenant_id` before DB operations.

### 2.4 Database (PostgreSQL 16)
*   **Single Source of Truth**: Recipes (DAGs), Inventory batches, Sales transactions, Forecasts, Draft POs, Schedules.
*   **RLS Enforcement**:
    *   Every table except `tenants` includes `tenant_id` UUID.
    *   **Policy Template**:
        ```sql
        CREATE POLICY tenant_isolation ON <table>
        USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
        ```
*   **Failure Mode**: If `tenant_id` is missing, queries must return zero rows, never fallback.

## 3. Ingestion Pipeline (Engine A) — Detailed Architecture

### 3.1 Request Flow
1.  **POS sends webhook** → `/webhooks/{source}`
2.  **API**:
    *   Validates signature
    *   Stores raw payload (for replay)
    *   Pushes message to `ingest` queue
    *   Responds `202 Accepted`
3.  **Worker**:
    *   Normalizes schema to Flux format
    *   If unknown POS item → insert into `triage_items`
    *   If known item → run **Recipe Explosion**
    *   Deduct inventory via **FEFO**

### 3.2 Ingestion Task Message Contract
```json
{
  "tenant_id": "<uuid>",
  "source": "square|toast|lightspeed",
  "payload_raw": { ... },
  "received_at": "<timestamp>",
  "replay_id": "<uuid|null>"
}
```
*   **Workers must assume**: replayable, idempotent, schema-bound.

### 3.3 Recipe Explosion Guarantee
Every ingestion step must produce **Ingredient-Level Usage Events**, derived via recursive CTE over recipes.

## 4. Tenant Isolation & DB Access Rules

### 4.1 Required API Middleware
`SET LOCAL app.current_tenant_id = <tenant_id>`
*   Applied on every request and every worker task.

### 4.2 Prohibited Operations
*   ❌ Raw SQL without `tenant_id`
*   ❌ Disabling RLS
*   ❌ Cross-tenant joins

## 5. Integration Contracts for Future Engines

### 5.1 Forecasting Engine (B)
*   API → Redis → Worker → DB rows appended to `forecasts`.

### 5.2 Inventory Engine (C)
*   Worker consumes `forecasts` → writes `draft_purchase_orders`.

### 5.3 Staffing Engine (D)
*   Worker consumes `forecasts` → solves OR-Tools CP-SAT → outputs `schedules`.

## 6. Repository Structure (Final)
```
flux-platform/
  services/
    api/
      routers/
      templates/
      static/
      main.py
    worker/
      engines/
         ingestion.py
         forecast.py
         inventory.py
         scheduling.py
      tasks.py
  lib/
    flux_lib/
      domain/
      models/
      utils/
  infrastructure/
    local/
      docker-compose.yml
    production/
      fly.toml or k8s/
  scripts/
  .github/workflows/
```
