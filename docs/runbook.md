# Silta Deployment Runbook

Operations manual for the Silta CNC manufacturing agent on Google Cloud Run.

## Service Overview

- **Service**: `silta` (Cloud Run)
- **Project**: `silta-hack`
- **Region**: `us-central1`
- **Runtime**: Python 3.12 + marimo 0.24.2 + CadQuery 2.5
- **Image Repository**: `us-central1-docker.pkg.dev/silta-hack/silta/silta`
- **Artifact Bucket**: `gs://silta-hack-silta-artifacts/`
- **Service Account**: `silta-run@silta-hack.iam.gserviceaccount.com`

## Deployment

### Prerequisites

1. Authenticated with gcloud:
   ```bash
   gcloud auth login
   gcloud config set project silta-hack
   ```

2. Environment has:
   - Git repository with clean working tree
   - `uv.lock` with pinned dependencies
   - `notebooks/workbench.py` (the marimo application)

### Deploy a New Version

```bash
bash scripts/deploy.sh
```

The script is **idempotent** and safe to run multiple times. It will:

1. Create Artifact Registry repo (if missing)
2. Create GCS bucket for artifacts (if missing)
3. Create runtime service account with minimal IAM grants (if missing)
4. Create Secret Manager secret for W&B API key (if missing, prompts for value)
5. Build image via Cloud Build and push to Artifact Registry
6. Deploy to Cloud Run with pinned commit-tagged image

**Time**: ~8-12 minutes for full build (cadquery/OCP is ~500MB). Subsequent deploys reuse cached layers.

**Expected cold-start time**: 15-30 seconds (large image with heavy dependencies).

### Verify Deployment

After deployment completes, the script prints the service URL. Run smoke tests:

```bash
python scripts/smoke_remote.py https://silta-<hash>-uc.a.run.app
```

This verifies:
- Root endpoint serves HTML without authentication
- Static assets (Three.js) served from app origin
- WebSocket endpoint exists
- No API keys leak in responses or headers
- Marimo editor routes are blocked (headless mode)

### View Logs

Stream real-time logs:
```bash
gcloud run services logs tail silta --region=us-central1 --follow
```

View last 100 lines:
```bash
gcloud run services logs read silta --region=us-central1 --limit=100
```

Filter errors only:
```bash
gcloud run services logs read silta --region=us-central1 --log-filter='severity>=ERROR'
```

## Rollback

### Quick Rollback to Previous Revision

Cloud Run keeps previous revisions. Find the last known-good revision:

```bash
gcloud run revisions list \
  --service=silta \
  --region=us-central1 \
  --limit=5
```

Roll back traffic to a specific revision:

```bash
gcloud run services update-traffic silta \
  --region=us-central1 \
  --to-revisions=silta-00042-abc=100
```

**Time**: ~10 seconds (traffic shift, no rebuild).

### Roll Back to a Specific Git Commit

If the previous revision is also broken, rebuild from a known-good commit:

```bash
git checkout <known-good-commit>
bash scripts/deploy.sh
```

This deploys a new revision with the older code. The image tag will be that commit's SHA.

### Emergency: Scale to Zero

If the service is misbehaving and causing spend or errors:

```bash
gcloud run services update silta \
  --region=us-central1 \
  --min-instances=0 \
  --max-instances=0
```

**Time**: ~5 seconds. All traffic will be rejected until you scale back up.

Restore:
```bash
gcloud run services update silta \
  --region=us-central1 \
  --min-instances=1 \
  --max-instances=1
```

## Secret Management

### Rotate W&B API Key

1. Generate new key at https://wandb.ai/settings
2. Add new secret version (does NOT overwrite existing):
   ```bash
   echo -n 'NEW_WANDB_KEY' | gcloud secrets versions add wandb-api-key --data-file=-
   ```
3. Deploy to pick up latest version (or wait for next deploy):
   ```bash
   bash scripts/deploy.sh
   ```
4. Verify new key works in logs:
   ```bash
   gcloud run services logs read silta --region=us-central1 --limit=50 | grep -i wandb
   ```
5. Disable old version once confident:
   ```bash
   gcloud secrets versions disable <VERSION_NUMBER> --secret=wandb-api-key
   ```

**Note**: Cloud Run references `latest` version of secret, so rotation is automatic on next deployment.

## Artifact Storage

### Where Artifacts Live

- **Ephemeral scratch**: `/tmp/artifacts` inside container (lost on instance replacement)
- **Durable storage**: `gs://silta-hack-silta-artifacts/`

Artifacts follow this structure:
```
gs://silta-hack-silta-artifacts/artifacts/<job-id>/
  ├── manifest.json
  ├── events.jsonl
  ├── target.step
  ├── target.stl
  ├── attempts/
  │   └── <attempt-id>.json
  └── trajectory-<attempt-id>.json
```

### Download a Job's Artifacts

```bash
JOB_ID="job-abc123"
gsutil -m cp -r "gs://silta-hack-silta-artifacts/artifacts/$JOB_ID" ./local-artifacts/
```

### Verify Artifact Integrity

The service computes SHA-256 hashes of all artifacts. To verify a STEP file:

```bash
gsutil cat "gs://silta-hack-silta-artifacts/artifacts/$JOB_ID/manifest.json" | jq -r '.cad_step_sha256'
gsutil cat "gs://silta-hack-silta-artifacts/artifacts/$JOB_ID/target.step" | sha256sum
```

Hashes must match.

### Clean Up Old Artifacts (Manual)

Cloud Storage has no lifecycle policy configured by default. To delete jobs older than 90 days:

```bash
# List old jobs (dry run)
gsutil ls -l "gs://silta-hack-silta-artifacts/artifacts/" | awk '$2 < "2026-06-01"'

# Delete (DESTRUCTIVE)
# gsutil -m rm -r "gs://silta-hack-silta-artifacts/artifacts/job-old-*"
```

**Recommendation**: Add a lifecycle rule after the event to auto-delete objects >90 days old.

## Cost Management

### Expected Costs (Rough Estimates)

- **Cloud Run**: ~$0.05/hour with min-instances=1 (2 vCPU, 4 GiB)
- **Cloud Storage**: ~$0.02/GB/month for artifacts
- **Cloud Build**: ~$0.003/build-minute (free tier: 120 build-minutes/day)
- **Secret Manager**: ~$0.06/secret/month + $0.03/10k accesses
- **Artifact Registry**: ~$0.10/GB/month storage

**Total baseline**: ~$35-50/month with one warm instance. Most cost is the warm instance.

### Post-Event Scale-Down

**CRITICAL**: After the hackathon event (T10+), scale down to save costs:

```bash
gcloud run services update silta \
  --region=us-central1 \
  --min-instances=0 \
  --max-instances=1
```

This allows cold starts (15-30s latency) but eliminates idle cost. Instance will auto-scale to 1 on first request.

For complete shutdown:
```bash
gcloud run services delete silta --region=us-central1
```

Artifacts in GCS and images in Artifact Registry remain. Redeploy with `bash scripts/deploy.sh` to restore.

### Monitor Spend

View current month's costs:
```bash
gcloud billing accounts list
gcloud billing projects describe silta-hack --format=json
```

Set up budget alerts in the Cloud Console:
https://console.cloud.google.com/billing/budgets?project=silta-hack

## Monitoring

### Health Checks

Cloud Run's built-in health check hits `/health` (marimo provides this).

Manual check:
```bash
curl -I https://silta-<hash>-uc.a.run.app/health
```

Expected: `HTTP/2 200`

### Performance Metrics

View in Cloud Console:
https://console.cloud.google.com/run/detail/us-central1/silta/metrics

Key metrics:
- **Request latency**: 50ms-2s (API), 5-60s (job runs)
- **Container startup time**: 15-30s (cold start)
- **CPU utilization**: 10-40% idle, 80-100% during CAD/simulation
- **Memory**: 1-2 GiB baseline, 3-4 GiB under load

### Error Tracking

Errors are logged to Cloud Logging. View:
```bash
gcloud run services logs read silta --region=us-central1 --log-filter='severity>=ERROR' --limit=50
```

Connect to W&B Weave for trace-level debugging (if telemetry is configured):
- W&B Project: `silta-squad` under `control-dev`
- Trace links are in job manifests: `manifest.weave_url`

## Troubleshooting

### Service Won't Start

1. Check logs for import errors:
   ```bash
   gcloud run services logs read silta --region=us-central1 --limit=100
   ```

2. Common issues:
   - **Missing system libs**: cadquery needs `libGL`, `libX11`, etc. Verify Dockerfile has them.
   - **Import failure**: Test in local build:
     ```bash
     docker build -t silta-test .
     docker run --rm silta-test python -c "import cadquery; import marimo; print('ok')"
     ```
   - **Secret not found**: Verify secret exists and has a version:
     ```bash
     gcloud secrets versions list wandb-api-key
     ```

### High Latency / Timeouts

- Check if instance is cold-starting (first request after idle):
  ```bash
  gcloud run services describe silta --region=us-central1 --format='value(status.conditions)'
  ```
- Increase min-instances if cold starts are unacceptable:
  ```bash
  gcloud run services update silta --region=us-central1 --min-instances=1
  ```

### Jobs Failing / Incorrect Results

1. Check W&B trace (if available): `manifest.weave_url`
2. Download job artifacts:
   ```bash
   gsutil -m cp -r "gs://silta-hack-silta-artifacts/artifacts/<job-id>" ./debug/
   ```
3. Replay locally:
   ```bash
   uv run python -c "from silta.service import default_service; ..."
   ```

### Out of Memory

Increase memory allocation:
```bash
gcloud run services update silta --region=us-central1 --memory=8Gi --cpu=4
```

**Note**: Cloud Run maximum is 32 GiB and 8 vCPU.

## Configuration

### Environment Variables

Set via `gcloud run services update`:

```bash
gcloud run services update silta --region=us-central1 \
  --set-env-vars="PLANNER_PROVIDER=wandb,PLANNER_MODEL=anthropic/claude-sonnet-4-5"
```

Current variables:
- `SILTA_ARTIFACT_BUCKET`: GCS bucket for durable artifacts
- `WANDB_PROJECT`: W&B project name
- `WANDB_ENTITY`: W&B organization
- `PLANNER_PROVIDER`: Inference provider (`wandb` or `openai`)
- `PLANNER_MODEL`: Model identifier for planner agent

### Update Service Configuration

Change CPU/memory/concurrency:
```bash
gcloud run services update silta \
  --region=us-central1 \
  --cpu=4 \
  --memory=8Gi \
  --concurrency=32
```

Change instance limits:
```bash
gcloud run services update silta \
  --region=us-central1 \
  --min-instances=0 \
  --max-instances=10
```

## Security

### IAM Permissions

The runtime service account (`silta-run@silta-hack.iam.gserviceaccount.com`) has:
- `roles/storage.objectAdmin` on artifact bucket only
- `roles/secretmanager.secretAccessor` on `wandb-api-key` secret only
- No project-wide roles

### Public Access

The service allows unauthenticated requests (`--allow-unauthenticated`) because judges must access it without a Google account. This is safe because:
- No destructive operations are exposed
- Inference budget limits are provider-side
- Session isolation prevents cross-session data access
- No editor UI (headless mode)

To restrict access post-event:
```bash
gcloud run services remove-iam-policy-binding silta \
  --region=us-central1 \
  --member="allUsers" \
  --role="roles/run.invoker"
```

Then access requires authentication:
```bash
curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://silta-<hash>-uc.a.run.app
```

## Support

### Logs and Diagnostics

- **Cloud Run logs**: `gcloud run services logs read silta --region=us-central1`
- **Build logs**: https://console.cloud.google.com/cloud-build/builds?project=silta-hack
- **W&B traces**: https://wandb.ai/control-dev/silta-squad (if configured)
- **Service details**: https://console.cloud.google.com/run/detail/us-central1/silta

### Rollback Decision Tree

1. **UI broken but service responsive**: Roll back to previous revision (10s)
2. **Service unresponsive**: Scale to zero, investigate, redeploy known-good commit
3. **Data corruption**: Restore artifacts from GCS versioned backups (if enabled)
4. **Secret compromised**: Rotate secret immediately, redeploy

### Post-Event Checklist

- [ ] Scale min-instances to 0
- [ ] Review Cloud Storage costs and set lifecycle policy
- [ ] Archive key job artifacts outside of GCS for long-term storage
- [ ] Disable or delete the service if no longer needed
- [ ] Review IAM permissions and remove unnecessary access
- [ ] Document lessons learned and update this runbook

## Appendix: Image Labels

Every image is labeled with:
- `org.opencontainers.image.revision`: Git commit SHA
- `dev.silta.lock-hash`: First 16 chars of `uv.lock` SHA-256

Inspect an image:
```bash
gcloud artifacts docker images describe \
  us-central1-docker.pkg.dev/silta-hack/silta/silta:latest \
  --format=json | jq '.image_summary.image.labels'
```

This allows auditing exactly what code/dependencies are deployed.
