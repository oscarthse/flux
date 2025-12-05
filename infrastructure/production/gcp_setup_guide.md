# Flux Platform: GCP Setup Guide

**Date:** December 5, 2025
**Target Environment:** Google Cloud Platform (GCP)

This guide provides the specific resource IDs and configuration steps to deploy the Flux Platform on GCP, replacing the AWS-centric instructions in the architecture document.

---

## 1. Database: Cloud SQL for PostgreSQL

You need to create a managed PostgreSQL instance.

*   **Product:** Cloud SQL
*   **Database Engine:** PostgreSQL 15 (or latest stable)
*   **Instance ID:** `flux-production-db` (Recommended)
*   **Password:** *[Generate a strong password]*
*   **Region:** `europe-west9` (Paris)
*   **Machine Type:** `db-custom-1-3840` (1 vCPU, 3.75 GB RAM) is sufficient for initial production.
*   **Storage:** SSD (Recommended 10GB+ with auto-increase).
*   **Connections:**
    *   **Public IP:** Disabled (Recommended for security).
    *   **Private IP:** Enabled (Select the `default` VPC network).

### **Action Item: Connection String**
Once created, construct your `DATABASE_URL`. It will look like this:
`postgresql://postgres:[PASSWORD]@[PRIVATE_IP_ADDRESS]:5432/flux`

*Note: You will need to create the database named `flux` inside the instance.*

---

## 2. Container Registry: Artifact Registry

You need a place to store your Docker images.

*   **Product:** Artifact Registry
*   **Format:** Docker
*   **Repository Name:** `flux-repo`
*   **Region:** `europe-west9`

### **Action Item: Image Tag**
Your Docker image path will change from `ghcr.io/...` to:
`europe-west9-docker.pkg.dev/[PROJECT_ID]/flux-repo/flux-api:latest`

*You will need to update `deployment.yaml` with this new image path.*

---

## 3. Kubernetes Cluster: Google Kubernetes Engine (GKE)

*   **Product:** GKE Autopilot (Recommended)
*   **Cluster Name:** `flux-cluster`
*   **Location:** Regional (`europe-west9`) for High Availability.
*   **Node Pools:** Managed automatically by Autopilot.
    *   **Note:** Autopilot will automatically provision nodes based on the resource requests and tolerations in your `deployment.yaml`.
    *   The `flux-worker` deployment's `tolerations` and `nodeSelector` will still work to isolate workloads, but you don't need to manually create a node pool.

---

## 4. Secrets Management

You must inject the database credentials into the cluster.

**Command:**
```bash
kubectl create secret generic flux-secrets \
  --from-literal=database-url='postgresql://postgres:[PASSWORD]@[PRIVATE_IP]:5432/flux' \
  --from-literal=secret-key='[GENERATE_RANDOM_KEY]'
```

---

## 5. Deployment Checklist

1.  **Build & Push:**
    ```bash
    gcloud auth configure-docker europe-west9-docker.pkg.dev
    docker build -t europe-west9-docker.pkg.dev/[PROJECT_ID]/flux-repo/flux-api:latest .
    docker push europe-west9-docker.pkg.dev/[PROJECT_ID]/flux-repo/flux-api:latest
    ```

2.  **Update Manifests:**
    *   Edit `infrastructure/production/deployment.yaml`: Replace `ghcr.io/flux-api:latest` with your new GCR image path.

3.  **Deploy:**
    ```bash
    kubectl apply -f infrastructure/production/deployment.yaml
    kubectl apply -f infrastructure/production/service.yaml
    # For GKE Ingress, you might use a ManagedCertificate and Ingress resource
    ```

---

## Summary of Identifiers

| Resource | Recommended ID / Value |
| :--- | :--- |
| **DB Instance** | `flux-production-db` |
| **DB Name** | `flux` |
| **Repo Name** | `flux-repo` |
| **Cluster Name** | `flux-cluster` |
| **Secret Name** | `flux-secrets` |
