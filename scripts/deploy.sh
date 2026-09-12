#!/usr/bin/env bash
# Idempotent deployment script for Silta on Google Cloud Run
# Safe to run multiple times - creates resources only if they don't exist

set -euo pipefail

# Configuration with defaults
PROJECT_ID="${GCP_PROJECT:-silta-hack}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-silta}"
ARTIFACT_REPO="${ARTIFACT_REPO:-silta}"
SA_NAME="${SA_NAME:-silta-run}"
SECRET_NAME="${SECRET_NAME:-wandb-api-key}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Silta Deployment Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Verify gcloud is authenticated and project is set
if ! gcloud config get-value project &>/dev/null; then
    echo "❌ ERROR: gcloud is not configured. Run: gcloud auth login"
    exit 1
fi

CURRENT_PROJECT=$(gcloud config get-value project)
if [[ "$CURRENT_PROJECT" != "$PROJECT_ID" ]]; then
    echo "❌ ERROR: Current project is $CURRENT_PROJECT, expected $PROJECT_ID"
    echo "Run: gcloud config set project $PROJECT_ID"
    exit 1
fi

echo "✓ Authenticated as: $(gcloud config get-value account)"
echo ""

# Step 1: Create Artifact Registry repository if it doesn't exist
echo "📦 [1/6] Artifact Registry repository..."
if gcloud artifacts repositories describe "$ARTIFACT_REPO" \
    --location="$REGION" &>/dev/null; then
    echo "  ✓ Repository '$ARTIFACT_REPO' already exists"
else
    echo "  Creating repository '$ARTIFACT_REPO'..."
    gcloud artifacts repositories create "$ARTIFACT_REPO" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Silta CNC agent container images"
    echo "  ✓ Created repository '$ARTIFACT_REPO'"
fi
echo ""

# Step 2: Create GCS bucket for artifacts
echo "🪣 [2/6] Cloud Storage bucket..."
BUCKET_NAME="${PROJECT_ID}-silta-artifacts"
if gsutil ls "gs://$BUCKET_NAME" &>/dev/null; then
    echo "  ✓ Bucket '$BUCKET_NAME' already exists"
else
    echo "  Creating bucket '$BUCKET_NAME'..."
    gsutil mb -p "$PROJECT_ID" -c STANDARD -l "$REGION" -b on "gs://$BUCKET_NAME"
    # Enable uniform bucket-level access
    gsutil uniformbucketlevelaccess set on "gs://$BUCKET_NAME"
    echo "  ✓ Created bucket '$BUCKET_NAME'"
fi
echo ""

# Step 3: Create runtime service account
echo "🔐 [3/6] Runtime service account..."
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "$SA_EMAIL" &>/dev/null; then
    echo "  ✓ Service account '$SA_EMAIL' already exists"
else
    echo "  Creating service account '$SA_NAME'..."
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="Silta Cloud Run runtime service account" \
        --description="Runtime identity for Silta service - artifact storage and secrets access only"
    echo "  ✓ Created service account '$SA_EMAIL'"
fi

# Grant bucket access
echo "  Granting objectAdmin on bucket..."
gsutil iam ch "serviceAccount:${SA_EMAIL}:roles/storage.objectAdmin" "gs://$BUCKET_NAME" || true

# Grant secret accessor role
echo "  Granting secret accessor..."
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None 2>/dev/null || echo "  (Secret may not exist yet - will retry after creation)"
echo ""

# Step 4: Create Secret Manager secret for W&B API key
echo "🔑 [4/6] Secret Manager secret..."
if gcloud secrets describe "$SECRET_NAME" &>/dev/null; then
    echo "  ✓ Secret '$SECRET_NAME' already exists"
    VERSION_COUNT=$(gcloud secrets versions list "$SECRET_NAME" --filter="state:enabled" --format="value(name)" | wc -l)
    if [[ "$VERSION_COUNT" -eq 0 ]]; then
        echo ""
        echo "  ⚠️  Secret exists but has no enabled versions."
        echo "  Add a version with:"
        echo "      echo -n 'YOUR_WANDB_API_KEY' | gcloud secrets versions add $SECRET_NAME --data-file=-"
        echo ""
    fi
else
    echo "  Creating secret '$SECRET_NAME'..."
    gcloud secrets create "$SECRET_NAME" \
        --replication-policy="user-managed" \
        --locations="$REGION" \
        --labels="app=silta,purpose=wandb-api"
    echo "  ✓ Created secret '$SECRET_NAME'"
    echo ""
    echo "  ⚠️  NOW ADD THE SECRET VALUE:"
    echo "      echo -n 'YOUR_WANDB_API_KEY' | gcloud secrets versions add $SECRET_NAME --data-file=-"
    echo ""
    echo "  The key must NOT contain a trailing newline (use echo -n)."
    echo "  NEVER commit the key to version control or expose it in logs."
    echo ""

    # Grant access now that the secret exists, even before it has a version.
    gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" \
        --condition=None
fi

# Wiring a secret with no enabled version makes the revision fail to start. Without a
# key the app runs on its deterministic planner and says so on screen, so deploy
# anyway rather than blocking on an external gate.
SECRET_VERSIONS=$(gcloud secrets versions list "$SECRET_NAME" \
    --filter="state:enabled" --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$SECRET_VERSIONS" -gt 0 ]]; then
    SECRET_FLAG=(--set-secrets="WANDB_API_KEY=${SECRET_NAME}:latest")
    echo "  ✓ Secret has $SECRET_VERSIONS enabled version(s); wiring it into the service"
else
    SECRET_FLAG=(--remove-secrets=WANDB_API_KEY)
    echo "  ⚠️  No secret version yet — deploying WITHOUT live inference."
fi
echo ""

# Step 5: Build and push image via Cloud Build
echo "🏗️  [5/6] Building container image..."
COMMIT_SHA=$(git rev-parse HEAD)
SHORT_SHA="${COMMIT_SHA:0:12}"
echo "  Git commit: $COMMIT_SHA"
echo "  Submitting build to Cloud Build..."
echo ""

gcloud builds submit \
    --config=cloudbuild.yaml \
    --region="$REGION" \
    --substitutions=COMMIT_SHA="$COMMIT_SHA" \
    --timeout=30m

BUILD_STATUS=$?
if [[ $BUILD_STATUS -ne 0 ]]; then
    echo ""
    echo "❌ Build failed. Check logs above or at:"
    echo "   https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID"
    exit 1
fi

IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${SERVICE_NAME}:${COMMIT_SHA}"
echo ""
echo "  ✓ Image built: $IMAGE_URL"

# Get image digest for verification
IMAGE_DIGEST=$(gcloud artifacts docker images describe "$IMAGE_URL" \
    --format='value(image_summary.digest)' 2>/dev/null || echo "unknown")
echo "  Image digest: $IMAGE_DIGEST"
echo ""

# Step 6: Deploy to Cloud Run
echo "🚀 [6/6] Deploying to Cloud Run..."

# Check if notebooks/workbench.py exists (required for deployment)
if [[ ! -f notebooks/workbench.py ]]; then
    echo "  ⚠️  WARNING: notebooks/workbench.py does not exist yet."
    echo "  Image is built but NOT deploying to Cloud Run."
    echo "  Deploy manually once the workbench is ready:"
    echo ""
    echo "      bash scripts/deploy.sh"
    echo ""
    exit 0
fi

# Prepare environment variables
ENV_VARS="SILTA_ARTIFACT_BUCKET=${BUCKET_NAME}"
ENV_VARS="${ENV_VARS},WANDB_PROJECT=${WANDB_PROJECT:-coreweave-hack-silta-squad}"
ENV_VARS="${ENV_VARS},WANDB_ENTITY=${WANDB_ENTITY:-silta}"
ENV_VARS="${ENV_VARS},PLANNER_PROVIDER=wandb"
# No speculative model id. Set WANDB_INFERENCE_MODEL only once `make models` has
# listed it and the credit grant is confirmed.
if [[ -n "${WANDB_INFERENCE_MODEL:-}" ]]; then
    ENV_VARS="${ENV_VARS},WANDB_INFERENCE_MODEL=${WANDB_INFERENCE_MODEL}"
fi

# Deploy the service
gcloud run deploy "$SERVICE_NAME" \
    --image="$IMAGE_URL" \
    --platform=managed \
    --region="$REGION" \
    --service-account="$SA_EMAIL" \
    --allow-unauthenticated \
    --cpu=2 \
    --memory=4Gi \
    --concurrency=16 \
    --min-instances=1 \
    --max-instances=1 \
    --timeout=3600 \
    --session-affinity \
    --set-env-vars="$ENV_VARS" \
    "${SECRET_FLAG[@]}" \
    --no-cpu-throttling \
    --execution-environment=gen2

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --platform=managed \
    --region="$REGION" \
    --format='value(status.url)')

REVISION=$(gcloud run services describe "$SERVICE_NAME" \
    --platform=managed \
    --region="$REGION" \
    --format='value(status.latestReadyRevisionName)')

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Service URL:    $SERVICE_URL"
echo "Revision:       $REVISION"
echo "Image:          $IMAGE_URL"
echo "Image digest:   $IMAGE_DIGEST"
echo "Git commit:     $COMMIT_SHA"
echo "Bucket:         gs://$BUCKET_NAME"
echo ""
echo "Next steps:"
echo "  1. Verify deployment: python scripts/smoke_remote.py $SERVICE_URL"
echo "  2. View logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo "  3. Monitor: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME"
echo ""
