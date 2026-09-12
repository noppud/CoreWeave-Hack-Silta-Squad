# Live deployment — required for completion

User requirement confirmed September 12, 2026: the application must be live. A laptop demo or recording alone does not complete implementation. Hosting choice: **GCP Cloud Run for the complete marimo/Python application**. Use its HTTPS service URL for judging; a custom domain is optional. Vercel remains an option if a separate frontend is later introduced, but is not needed for this architecture.

## Architecture

- Build a Linux container with locked Python/CadQuery dependencies and bundled viewer assets. Run marimo in application mode, bound to `0.0.0.0` and the supplied `PORT`; never expose the notebook editor. Verify exact flags with the pinned version. [marimo Docker deployment](https://docs.marimo.io/guides/deploying/deploying_docker/).
- Store images in Artifact Registry; build through Cloud Build or an equivalent reproducible CI step. Label image/revision with commit and dependency lock hash.
- Serve chat, viewer, application services and read-only evaluation results from one Cloud Run service. Keep inference keys server-side in Secret Manager. Give the runtime service account access only to the required secrets and artifact bucket. [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets).
- Store completed input/output bundles and manifests in a private Cloud Storage bucket. Use per-job object keys and upload immutable content before publishing its completed manifest. Serve downloads through session-authorized application code. Local files are scratch/cache; Cloud Run's writable filesystem is ephemeral. [Container contract](https://docs.cloud.google.com/run/docs/container-contract).
- Permit public access to the demo surface. Keep batch evaluation and unrestricted spend controls out of the public application. Use session-scoped job/artifact access, bounded uploads, request limits and provider-side spend limits. Judges should not need a Google account.

## Initial service configuration

Proposed starting point, to measure during deployment: 2 vCPU, 4 GiB RAM, at most two active compute jobs per instance, request concurrency 16, one warm instance during the event and maximum one normal serving instance. Start in an available US region near the demo audience; choose an existing authorized project. These are resource settings, not a price quote; verify cost and quotas before provisioning. Do not assume the inference-credit offer covers GCP hosting.

Cloud Run supports WebSockets, but connections are subject to request timeout and affinity is best-effort. Configure a 3,600-second connection timeout and session affinity; retain the separate 120-second job deadline. Reconnect must recover completed runs from durable artifacts, not assume the same process still exists. [Cloud Run WebSockets](https://docs.cloud.google.com/run/docs/triggering/websockets).

Do not rely on one instance as a durable lock or exact global spend cap: replacement/deployment can overlap instances. Use unique job IDs, create-only/conditional manifest publication, per-job call limits and provider-enforced account budget limits. On process loss, mark an interrupted job incomplete; offer an explicit new run. Automatic continuation of in-flight model calls is outside MVP. Avoid deployments during the three-minute presentation.

## Delivery sequence

1. T00: verify GCP project/account access, billing/quota, container CAD compatibility and permitted service settings. Keep those as explicit deployment gates; implementation can proceed independently.
2. Immediately after T05: build and deploy the first chat/CAD/check slice to a real HTTPS URL. Verify WebSocket updates and a STEP download remotely before adding the full simulator.
3. Integrate simulator and ARIA/evaluation results into the same deployment. Runtime keys remain out of image layers, build logs, HTML and JavaScript. Keep live evaluation execution operator-only.
4. T08: deploy a release image; run the remote acceptance flow below; record commit, image digest, revision, URL and smoke-test job ID. Keep the previous known-good revision for rollback.
5. T09: put the verified URL in README and submission. Retain local replay/recording as presentation backup. Set an explicit post-event warm-instance/spend review date.

## Acceptance gate

The implementation is live only when a fresh browser session can:

- Open the HTTPS app without developer-local resources or a Google login.
- Upload/use the demo drawing, clarify dimensions, run real model planning and repairs, and see progress.
- View actual collision/stock-removal results and download valid STEP/recipe/report artifacts.
- Open a completed run after browser reconnect and after a service revision restart.
- Keep two browser sessions' job state and private artifacts separate.
- Receive clear bounded failure on provider timeout/cancellation/compute saturation without a false success.
- Follow working sponsor evidence links or view scrubbed embedded evidence where sponsor access is restricted.

Record results against the deployed revision, not only localhost. A successful container build, HTTP 200, static landing page, or replay-only site is insufficient. If Cloud Run cannot pass the CAD/WebSocket spike within its timebox, deploy the same container to a suitable GCP VM or another container host; retain the live-URL requirement.


## Public presentation routes

The container now starts `uvicorn silta.web:app` with one worker. The existing
workbench remains at `/`; the seven-slide judge presentation is at `/slides/`,
Joel's four-slide notebook is at `/demo/`, and the generated pitch/eval reports
are served from an explicit allowlist under `/presentation/`. Interactive batch
evaluation is not mounted publicly. `/health` reports the deployed source commit.
All presentation links use hosted routes in this configuration.

- [Live slideshow](https://silta-cdswwreljq-uc.a.run.app/slides/)
- [Live pitch guide](https://silta-cdswwreljq-uc.a.run.app/presentation/guide.html)
- [Live eval evidence](https://silta-cdswwreljq-uc.a.run.app/presentation/evals.html)

Deploy an image update to the existing Cloud Run service while retaining its
runtime identity, secrets, inference model, bucket, and resource settings.
