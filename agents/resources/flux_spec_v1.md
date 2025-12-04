# Flux Restaurant Analytics Platform v1.0 Specification

## 0. Global Goal & Constraints
**Goal**: Implement the Flux Restaurant Analytics Platform v1.0 exactly as specified: ingestion → forecasting → inventory → staffing → HTMX UI → infra & CI.

**Principles**:
*   Every non-trivial decision is peer-reviewed by at least one other specialized agent.
*   All math/ops research is derived, checked, and simulated before touching production engines.
*   All code passes design review → code review → tests → integration checks.
*   **Safety rails**: RLS, multi-tenancy, data isolation, and performance guarantees (API <100ms, worker offloaded).

## 1. Agent Roster
### 1.1 Orchestrator Agent [ORCH]
*   **Objective**: Coordinate all other agents to implement the Flux spec in phases.
*   **Inputs**: The full v1.0 spec; current phase (1–4); backlog; previous agent outputs.
*   **Outputs**: Phase-scoped tasks, assignments, merge decisions.
*   **Checks**: Ensures deliverable lifecycle (spec→design→impl→test→review→docs). Blocks merging if reviewers flag issues.

### 1.2 System Architect [ARCH]
*   **Objective**: Keep implementation aligned with architectural principles.
*   **Inputs**: Flux spec, phase goals, DB schema.
*   **Outputs**: Architecture diagrams, design docs, interface contracts.
*   **Checks**: Validates async flows, repo structure, no heavy compute in API.

### 1.3 Data / DB Architect [DATA]
*   **Objective**: Design and maintain PostgreSQL 16 schema.
*   **Inputs**: Domain spec (RLS, recipes, inventory).
*   **Outputs**: SQL DDL, RLS policies, DB constraints/indexes.
*   **Checks**: RLS isolation, recursive CTE correctness.

### 1.4 ML / Forecasting Specialist [ML]
*   **Objective**: Implement Engine B (Forecasting).
*   **Inputs**: Sales schema, feature list.
*   **Outputs**: Math spec, `forecast.py`, evaluation strategy.
*   **Checks**: Hybrid switch logic, backtests, idempotent jobs.

### 1.5 Inventory Optimization Specialist [INV_OPT]
*   **Objective**: Implement Engine C (R,S policy, FEFO).
*   **Inputs**: Inventory model, forecasts.
*   **Outputs**: Demand derivations, safety stock formulas, `inventory.py`.
*   **Checks**: Math correctness, scenario simulations, draft PO accuracy.

### 1.6 Staffing / Scheduling Specialist [STAFF_OPT]
*   **Objective**: Implement Engine D with OR-Tools CP-SAT.
*   **Inputs**: Forecasts, labor constraints.
*   **Outputs**: Constraint model, `scheduling.py`.
*   **Checks**: Hard constraint enforcement, penalty structure validation.

### 1.7 Backend Engineer [BACKEND]
*   **Objective**: Implement FastAPI API, Dramatiq worker, shared lib.
*   **Inputs**: Arch specs, engine APIs.
*   **Outputs**: Routes, tasks, Pydantic/ORM models.
*   **Checks**: Latency <100ms, idempotency, tenant context propagation.

### 1.8 UI / HTMX Engineer [UI]
*   **Objective**: Implement Triage Room, Smart Order, Reliability Badge.
*   **Inputs**: UX flows.
*   **Outputs**: Jinja templates, HTMX endpoints.
*   **Checks**: No heavy client logic, accessibility.

### 1.9 DevOps & Infra [DEVOPS]
*   **Objective**: Implement infra, docker-compose, CI.
*   **Inputs**: Service layout.
*   **Outputs**: `docker-compose.yml`, CI pipelines, prod manifests.
*   **Checks**: Secrets management, healthchecks, CI jobs.

### 1.10 QA & Test Engineer [QA]
*   **Objective**: Define test strategy and enforce quality.
*   **Inputs**: Specs, schema, engines.
*   **Outputs**: Test plans, fixtures, automated tests.
*   **Checks**: Coverage thresholds, edge cases, regression tests.

### 1.11 Math & Analytics Auditor [MATH_AUDIT]
*   **Objective**: Audit math and trust metrics.
*   **Inputs**: Derivations, simulation results.
*   **Outputs**: Independent derivations, critiques, sanity dashboards.
*   **Checks**: No magic constants, documented formulas, theoretical alignment.

### 1.12 Security / RLS Auditor [SEC]
*   **Objective**: Guarantee isolation and auth.
*   **Inputs**: RLS configs, auth flows.
*   **Outputs**: Threat model, penetration tests.
*   **Checks**: RLS enforcement, auth checks, red team tests.

### 1.13 Documentation & DX Agent [DOCS]
*   **Objective**: Maintain documentation and DX.
*   **Inputs**: Agent outputs.
*   **Outputs**: README, ADRs, docstrings.
*   **Checks**: Doc coverage, onboarding ease.

## 2. Global Workflow Pattern
1.  **Clarify & Slice**: [ORCH] defines slice, [ARCH]+[DATA] define contracts.
2.  **Design**: Specialist writes spec; [MATH_AUDIT]/[SEC]/[QA] review.
3.  **Implementation**: Code written and locally tested.
4.  **Peer Review**: Domain specialist + Cross-cutting reviewer ([QA]/[MATH_AUDIT]/[SEC]).
5.  **Tests & CI**: [QA] ensures tests, [DEVOPS] ensures CI, [ORCH] blocks on red.
6.  **Docs & Release**: [DOCS] updates docs, [ORCH] marks complete.

## 3. Phase-By-Phase Plan
### Phase 1: Foundation & Ingestion
*   **Goal**: RLS DB + Ingestion + Triage + Recipe Editor.
*   **Key Tasks**: DB Schema, RLS, POS Webhooks, Ingestion Strategy, Triage UI.

### Phase 2: Forecasting Loop
*   **Goal**: Prophet + XGBoost + Hybrid Switch.
*   **Key Tasks**: Feature engineering, Model implementation, Backtesting, Reliability Badge.

### Phase 3: Inventory Optimization
*   **Goal**: R,S Policy + Smart Order Dashboard.
*   **Key Tasks**: R/S formulas, FEFO logic, Draft PO generation, Smart Order UI.

### Phase 4: Staffing & Polish
*   **Goal**: CP-SAT Scheduling + Roster.
*   **Key Tasks**: Constraint model, Schedule generation, Roster UI, Notifications.
