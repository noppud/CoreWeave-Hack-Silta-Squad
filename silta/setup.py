"""Independent sponsor setup checks; no product idea or model calls required."""

import argparse
import os

from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--models", action="store_true", help="List models from W&B Inference.")
    mode.add_argument("--trace", action="store_true", help="Send a synthetic setup trace to Weave.")
    args = parser.parse_args()
    load_dotenv()
    names = ("WANDB_API_KEY", "WANDB_ENTITY", "WANDB_PROJECT", "WANDB_INFERENCE_MODEL")
    settings = {name: os.environ.get(name, "").strip() for name in names}
    if not args.models and not args.trace:
        for name, value in settings.items():
            print(f"{name}: {'configured' if value else 'missing'}")
        print("Local configuration only; account access, credits, and traces are not verified.")
        parser.exit(0 if all(settings.values()) else 1)

    missing = [name for name in names[:3] if not settings[name]]
    if missing:
        parser.error("Set these values in .env: " + ", ".join(missing))
    project = f"{settings['WANDB_ENTITY']}/{settings['WANDB_PROJECT']}"
    if args.models:
        import httpx

        try:
            response = httpx.get(
                "https://api.inference.wandb.ai/v1/models",
                headers={
                    "Authorization": f"Bearer {settings['WANDB_API_KEY']}",
                    "OpenAI-Project": project,
                },
                timeout=30,
            )
            response.raise_for_status()
            model_ids = [model["id"] for model in response.json()["data"]]
            if not model_ids or not all(isinstance(model, str) for model in model_ids):
                raise ValueError("No usable model IDs")
        except httpx.HTTPStatusError as exc:
            parser.exit(1, f"Model listing failed: HTTP {exc.response.status_code}.\n")
        except (httpx.RequestError, ValueError, KeyError, TypeError):
            parser.exit(1, "Model listing failed: connection or response error.\n")
        print("\n".join(sorted(model_ids)))
        print("Set WANDB_INFERENCE_MODEL to a listed ID. Listing does not verify credit balance.")
        return

    import weave

    client = weave.init(project)

    @weave.op()
    def setup_smoke(message: str) -> dict:
        return {"message": message, "purpose": "synthetic setup check", "inference_calls": 0}

    setup_smoke("Silta Squad boilerplate connection check")
    client.flush()
    print(f"Trace flush completed. Verify setup_smoke at https://wandb.ai/{project}/weave")
    print("No inference call was made; inference credits are still unverified.")


if __name__ == "__main__":
    main()
