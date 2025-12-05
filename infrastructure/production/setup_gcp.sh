#!/bin/bash
# Flux Platform - GCP Infrastructure Setup Script
# Usage: ./setup_gcp.sh [PROJECT_ID]

set -e

PROJECT_ID=$1
REGION="europe-west9"
ZONE="europe-west9-a"
DB_INSTANCE="flux-production-db"
CLUSTER_NAME="flux-cluster"
REPO_NAME="flux-repo"

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: $0 [PROJECT_ID]"
    exit 1
fi

echo "🚀 Starting Flux Platform GCP Setup for project: $PROJECT_ID"

# 1. Enable APIs
echo "📦 Enabling necessary APIs..."
gcloud services enable \
    compute.googleapis.com \
    container.googleapis.com \
    sqladmin.googleapis.com \
    artifactregistry.googleapis.com \
    servicenetworking.googleapis.com \
    --project "$PROJECT_ID"

# 2. Create Artifact Registry
echo "🐳 Creating Artifact Registry..."
if ! gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Flux Platform Docker Repository" \
        --project="$PROJECT_ID"
    echo "✅ Artifact Registry created."
else
    echo "✅ Artifact Registry already exists."
fi

# 3. Create Cloud SQL Instance
echo "🗄️  Creating Cloud SQL Instance (This may take 10-15 minutes)..."
if ! gcloud sql instances describe "$DB_INSTANCE" --project="$PROJECT_ID" &>/dev/null; then
    # Create private IP connection
    gcloud compute addresses create google-managed-services-default \
        --global \
        --purpose=VPC_PEERING \
        --prefix-length=16 \
        --description="Peering for Google Cloud SQL" \
        --network=default \
        --project="$PROJECT_ID" || true

    gcloud services vpc-peerings connect \
        --service=servicenetworking.googleapis.com \
        --ranges=google-managed-services-default \
        --network=default \
        --project="$PROJECT_ID" || true

    # Create Instance
    gcloud sql instances create "$DB_INSTANCE" \
        --database-version=POSTGRES_15 \
        --tier=db-custom-1-3840 \
        --region="$REGION" \
        --storage-type=SSD \
        --storage-size=10 \
        --root-password="change-me-immediately" \
        --network=default \
        --no-assign-ip \
        --project="$PROJECT_ID"

    # Create Database
    gcloud sql databases create flux --instance="$DB_INSTANCE" --project="$PROJECT_ID"
    echo "✅ Cloud SQL created."
else
    echo "✅ Cloud SQL instance already exists."
fi

# 4. Create GKE Cluster
echo "☸️  Creating GKE Cluster (This may take 10-15 minutes)..."
if ! gcloud container clusters describe "$CLUSTER_NAME" --region="$REGION" --project="$PROJECT_ID" &>/dev/null; then
    # Create GKE Autopilot Cluster
    # Autopilot automatically manages nodes, security, and scaling.
    # We don't need to define node pools manually.
    gcloud container clusters create-auto "$CLUSTER_NAME" \
        --region "$REGION" \
        --project "$PROJECT_ID"

    echo "✅ GKE Autopilot Cluster created."
else
    echo "✅ GKE Cluster already exists."
fi

# 5. Configure kubectl
echo "🔌 Configuring kubectl..."
gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$REGION" --project "$PROJECT_ID"

echo "🎉 Setup Complete!"
echo "------------------------------------------------"
echo "Next Steps:"
echo "1. Change the DB password: gcloud sql users set-password postgres --instance=$DB_INSTANCE --password='YOUR_NEW_PASSWORD'"
echo "2. Get the DB Private IP: gcloud sql instances describe $DB_INSTANCE --format='get(ipAddresses[0].ipAddress)'"
echo "3. Run: kubectl create secret generic flux-secrets --from-literal=database-url='postgresql://postgres:PASSWORD@IP:5432/flux' --from-literal=secret-key='random-key'"
echo "4. Build and push your image."
echo "5. Apply manifests."
