# Flux Platform: Production Deployment Architecture

**Version:** 1.0.0
**Date:** December 5, 2025
**Status:** Approved for Implementation

---

# I. Core Hosting Strategy (The "Normal Website" Mandate)

**Goal:** The user must experience the platform as a fast, reliable website, indistinguishable from a standard SaaS application, despite the complex AI operations running in the background.

## 1. Cloud Provider: AWS (Amazon Web Services)
**Justification:** AWS is chosen for its maturity, global availability zones, and robust managed services (EKS, RDS) that minimize operational overhead. It provides the elastic scalability required to handle spikey workloads from the forecasting engine.

## 2. Hosting Platform: Amazon EKS (Elastic Kubernetes Service)
**Role:** Container Orchestration.
**Why K8s?** Kubernetes abstracts the underlying infrastructure, allowing us to define the "desired state" of our application (e.g., "always run 3 copies of the API"). It handles self-healing (restarting crashed containers) and zero-downtime deployments automatically.

## 3. Frontend Access: AWS Application Load Balancer (ALB)
**Role:** The Entry Point.
**Function:**
*   **SSL Termination:** Decrypts HTTPS traffic at the edge, offloading CPU work from the application.
*   **Routing:** Directs traffic to the correct service (API vs. Static Assets).
*   **Single URL:** Provides a stable entry point (`app.flux-platform.com`) regardless of the dynamic IP addresses of the underlying pods.

---

# II. Service Deployment Architecture

The application is split into three distinct components to ensure that heavy AI processing never degrades the user experience.

## 1. API Service (High Availability)
*   **Purpose:** Serves the Dashboard, Inventory UI, and handles all synchronous HTMX requests.
*   **Configuration:**
    *   **Replicas:** Minimum of **3 Replicas** spread across 3 Availability Zones (AZs). This ensures that if one data center fails, the application remains online.
    *   **Resources:** Optimized for high memory (caching) and moderate CPU.
*   **Resilience (Probes):**
    *   **Liveness Probe:** Checks `/health` every 10 seconds. If it fails 3 times, K8s kills and restarts the pod.
    *   **Readiness Probe:** Checks if the database connection is active. K8s will not send user traffic to a pod until this passes, preventing "500 Internal Server Error" during startup.

## 2. Worker Service (CPU-Bound / Asynchronous)
*   **Purpose:** Executes heavy background tasks: Prophet model training, WMAPE calculation, and large-scale Recipe Explosion.
*   **Isolation:**
    *   **Node Pool:** Deployed on a **Dedicated Node Pool** (e.g., `c5.xlarge` instances) with Taints and Tolerations. This physically separates the worker workloads from the API, ensuring that 100% CPU usage during training does not slow down the dashboard.
*   **Job Strategy:**
    *   **CronJobs:** Scheduled K8s Jobs trigger the daily forecasting pipeline at 2:00 AM local time.
    *   **Queues:** Dramatiq workers process ad-hoc tasks (e.g., "Recalculate Inventory") triggered by user actions.

## 3. Data Service (Managed Persistence)
*   **Platform:** **Amazon RDS for PostgreSQL** (Managed Service).
*   **Configuration:** Multi-AZ deployment for automatic failover.
*   **Security:**
    *   **Private Subnet:** The database has **NO public IP address**.
    *   **Security Groups:** Firewall rules allow inbound traffic *only* from the K8s Cluster Security Group on port 5432.

---

# III. CI/CD and Operational Plan (The Automation)

We utilize a GitOps-style workflow where the `main` branch is the source of truth.

## 1. Deployment Strategy: Rolling Updates
**Objective:** Zero Downtime.
**Mechanism:**
1.  K8s spins up a new pod (Version B).
2.  K8s waits for the **Readiness Probe** to pass (DB connected, app initialized).
3.  Once ready, K8s directs traffic to Version B and terminates one Version A pod.
4.  This repeats until all pods are Version B. Users never experience an outage.

## 2. Security & Secrets
**Mechanism:** Kubernetes Secrets (encrypted at rest).
**Workflow:**
*   Sensitive data (DB passwords, API keys) are never committed to Git.
*   They are injected into the K8s cluster via a secure pipeline (e.g., GitHub Actions Secrets or AWS Secrets Manager).
*   The application reads them as Environment Variables (`DB_PASSWORD`, `SECRET_KEY`).

## 3. The Zero-Downtime Pipeline
**Trigger:** Push to `main` branch.

1.  **Test (CI):**
    *   Run `pytest tests/unit` and `pytest tests/integration`.
    *   **Gate:** Pipeline stops if any test fails.
2.  **Build:**
    *   Build Docker image: `docker build -t ghcr.io/flux-api:${COMMIT_SHA} .`
    *   Push to Container Registry.
3.  **Deploy (CD):**
    *   Update the K8s Deployment manifest with the new image tag.
    *   Command: `kubectl apply -f infrastructure/production/deployment.yaml`
    *   K8s initiates the **Rolling Update**.

---

# IV. Monitoring and Observability (The Trust Layer)

To maintain the "Antigravity" standard, we must know about issues *before* the user does.

## 1. APM (Application Performance Monitoring)
*   **Tool:** **Datadog** or **Prometheus/Grafana**.
*   **Key Metrics:**
    *   **API Latency:** Alert if p95 latency > **100ms** (Critical for HTMX "instant" feel).
    *   **Error Rate:** Alert if 5xx errors > 1%.
    *   **Pod Restarts:** Alert if pods are crashing frequently (LoopCrashBackOff).

## 2. Logic Trust Monitoring
*   **Purpose:** Verifying the *correctness* of the AI, not just the uptime of the server.
*   **Checks:**
    *   **Prophet Job Completion:** Alert if the daily forecasting job has not completed by 4:00 AM.
    *   **WMAPE Threshold:** Alert if the model's accuracy drops below **85%** (WMAPE > 0.15). This indicates a "Logic Schism" or data drift that requires engineering intervention.
