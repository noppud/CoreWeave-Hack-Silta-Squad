# Sandbox access check

**Historical access investigation.** The user reported a service bug and authorized changing the plan on September 12. Hosted Sandboxes are no longer a build dependency; the controlled demo uses local Python check processes. Weave remains in use. The support request below was not sent.

Checked September 12, 2026 against the authenticated W&B organization UI and a
live `cwsandbox` request.

- Organization: `silta-org`; team: `silta`.
- Touko's organization role is **Admin**, with full Models and Weave access.
- Organization and team settings expose no serverless sandbox activation switch.
- The signed-in Home → Serverless Sandboxes page says organization access must
  be requested from `support@wandb.com`.
- A minimal explicit `placement_mode="serverless"` request using the existing
  W&B key returned `Permission denied: sandboxes not enabled for this organization`.
- No account settings or roles were changed. No new sandbox was created.

Activation request, ready to send with user authorization:

> Please enable W&B Serverless Sandboxes public-preview access for organization
> `silta-org`, team `silta`, for our CoreWeave hackathon project
> `coreweave-hack-silta-squad`. We are organization admins. A valid W&B API key
> works with Weave, but `cwsandbox.Sandbox.run(placement_mode="serverless")`
> returns “Permission denied: sandboxes not enabled for this organization.”

The request above has **not been sent**.

Sources: [W&B creation guide](https://docs.wandb.ai/sandboxes/create-sandbox),
[CoreWeave serverless setup](https://docs.coreweave.com/products/sandboxes/get-started).
The latter distinguishes W&B credentials (no extra IAM grant once the org is
enabled) from CoreWeave API tokens (`SANDBOX_USER` required).
