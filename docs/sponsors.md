# Sponsor setup and credits

Checked September 12, 2026 against the saved participant handbook, official sponsor documentation, the live credit form, and the signed-in W&B team page. The handbook's June 6–7 schedule is stale for this workspace; reconfirm event offers onsite.

## Tool and credit map

| Tool | What it provides | Offer / activation | Boilerplate status |
| --- | --- | --- | --- |
| W&B Weave | Agent traces and evaluations; satisfies the handbook's W&B usage requirement when actually used | W&B account and API key. No separate Weave dollar grant stated in the handbook. | SDK installed; agent tracing wired; `make trace` sends a synthetic setup trace without inference. |
| W&B / CoreWeave Serverless Inference | Hosted models through an OpenAI-compatible API | Handbook offers **$100**. Submit the credit form, then find Anna or Lorenzo in yellow bomber jackets to raise quota. More can be requested. | Client wired; `make models` discovers model IDs. Credit grant and live inference not yet verified. |
| W&B MCP server | Let a coding agent inspect runs, traces, evaluations, and documentation | Hosted endpoint uses the W&B API key. No separate credit grant stated. | Connection recipe below; no W&B MCP tools are exposed in this assistant session yet. |
| ARIA | Analyze W&B experiments and recommend next iterations | Runs in team projects on W&B Multi-tenant Cloud; organization admin must enable Smart features. No separate credit grant stated. | Team page shows Ask ARIA. A useful project conversation and experiment access are not yet verified. |
| marimo / molab | Python notebooks and hosted compute | Saved handbook says molab is free and everyone gets a GPU. Exact GPU, quota, and runtime limits are not specified; confirm with sponsor. | `make notebook` opens an optional local editor. Hosted molab login and GPU allocation remain separate. |
| TypeSafe AI | Sponsor model access | **The same live credit form includes TypeSafe AI.** Select it, then talk to the TypeSafe team for model access. No dollar amount, endpoint, SDK, or quota is stated. | Wait for sponsor access details before adding an adapter or guessing configuration. |
| CoreWeave GPU infrastructure | Potential infrastructure beyond hosted inference | No separate CoreWeave cloud/GPU credit grant is specified in the saved handbook. The named free GPU offer is molab. | No cloud cluster or paid infrastructure provisioned. |

Sources: [Weave](https://docs.wandb.ai/weave/quickstart), [Inference](https://docs.wandb.ai/inference/api-reference), [W&B MCP](https://github.com/wandb/wandb-mcp-server), [ARIA](https://docs.wandb.ai/aria/overview), [marimo](https://docs.marimo.io/getting_started/), [molab](https://molab.marimo.io/), [TypeSafe](https://typesafe.ai/).

## Claim the hackathon credits

[Open the organizer credit request form](https://docs.google.com/forms/d/e/1FAIpQLSeTSFIuiOCGyAbQ3DpnCJaiyATkpDeOHdzD915QlH4J7x0CrQ/viewform).

The live form covers **both W&B Inference and TypeSafe AI**, even though the handbook introduces the link as an inference credit form. It asks for:

1. Your Google account email and W&B organization email.
2. Person/team name (use the agreed team name).
3. Initial Request or Credit Bump.
4. W&B Inference, TypeSafe AI, or both.
5. Hackathon-only use agreement and acceptance of both providers' privacy policies and terms.

After submission, find Anna or Lorenzo for inference quota and the TypeSafe team for their model access. A form submission is not proof of activated credits. Record confirmation and inspect the correct organization's inference balance before calling the grant active. Account trial days, a model listing, and an API key do not establish the $100 grant.

No form has been submitted by this bootstrap. Each user must review the form's terms before accepting them.

## W&B setup before choosing the idea

The signed-in team page confirms `konstav-control-dev` is a team under organization `konstav-control-dev-org`. Use the **team** slug for `WANDB_ENTITY`. The template project name is `coreweave-hack-silta-squad`; the project URL is a target until the first trace is verified.

```sh
make setup          # Creates .env once; installs locked dependencies
# Add WANDB_API_KEY in .env; never paste a real key into tracked files
make doctor         # Local settings only, no network; missing settings return exit code 1
make models         # Read model catalog; does not require a selected model
# Set WANDB_INFERENCE_MODEL in .env to a returned ID
make trace          # Writes one synthetic trace; no model call or inference credit use
make demo           # Three inference calls by default; consumes credits
make check          # Lint, formatting, and offline tests
```

Weave can create the configured project on first initialization. Open its trace view and verify `setup_smoke` before recording tracing as working. The inference model remains configurable so the team can choose based on the idea, model availability, and sponsor guidance.

## W&B MCP

Use the [official hosted server instructions](https://github.com/wandb/wandb-mcp-server#quick-start) for your coding tool:

- Transport: HTTP
- Server URL: `https://mcp.withwandb.com/mcp`
- Authentication: bearer token sourced from `WANDB_API_KEY`
- Scope your queries to `konstav-control-dev/coreweave-hack-silta-squad`.

Keep the API key in the client's secret/environment configuration. Once connected, ask it to list the team's projects, then inspect the setup trace. The available tools include reads and writes; connecting the server is separate from authorizing it to create reports or log new analysis.

The handbook also links the optional [Weavify skill](https://github.com/altryne/weavify-skill) and the [MCP/OpenTelemetry example](https://github.com/altryne/mcp-otel). They are resources, not required dependencies. The starter already instruments its loop directly.

## Optional tools after the idea is locked

- **ARIA:** use Ask ARIA in the team's actual experiment project to compare baseline and revised results. Confirm Smart features with the organization admin if unavailable. Experiment execution has additional setup; seeing the button is not proof it can run experiments.
- **marimo:** run `make notebook` for local exploration, or use molab for the hosted/GPU path. The optional editor resolves marimo on demand; if selected for the project, pin it in the project lockfile and commit the notebook as Python source.
- **TypeSafe:** obtain base URL, authentication method, model ID, quota/expiry, and one working example from its onsite engineer. Add a provider adapter only after those are known.

## Ready to build

- [ ] API key configured locally for the verified team.
- [ ] Credit request completed and organizer activation confirmed.
- [ ] Model catalog fetched; model selected.
- [ ] Synthetic Weave trace visible in the team project.
- [ ] One real inference loop succeeded with visible traces.
- [ ] Optional sponsor access verified for tools chosen by the team.
- [ ] Idea, measurable evaluation, owners, and track entered in [the build plan](plan.md).

Then replace the sample loop's task/evaluator and add the product UI. Keep sponsor integrations and submission evidence in place.
