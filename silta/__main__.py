"""Run with `uv run python -m silta --help`."""

import argparse
import json
import os

from dotenv import load_dotenv

from silta.loop import run_loop


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small agent loop traced in W&B Weave.")
    parser.add_argument(
        "task", nargs="?", default="Explain a useful agent feedback loop in 3 bullets."
    )
    parser.add_argument("--rounds", type=int, choices=range(1, 4), default=1)
    parser.add_argument(
        "--check", action="store_true", help="Validate config without network calls."
    )
    args = parser.parse_args()
    if not args.task.strip():
        parser.error("Task must not be empty.")

    load_dotenv()
    required = ("WANDB_API_KEY", "WANDB_ENTITY", "WANDB_PROJECT", "WANDB_INFERENCE_MODEL")
    config = {name: os.environ.get(name, "").strip() for name in required}
    missing = [name for name, value in config.items() if not value]
    if missing:
        parser.error("Set these values in .env: " + ", ".join(missing))
    project = f"{config['WANDB_ENTITY']}/{config['WANDB_PROJECT']}"
    if args.check:
        print("Required configuration is present. Credentials and model access are not verified.")
        return

    import httpx
    import weave

    weave.init(project)
    with httpx.Client(
        base_url="https://api.inference.wandb.ai/v1/",
        headers={
            "Authorization": f"Bearer {config['WANDB_API_KEY']}",
            "OpenAI-Project": project,
        },
        timeout=60.0,
    ) as client:

        @weave.op()
        def complete(system: str, prompt: str) -> str:
            response = client.post(
                "chat/completions",
                json={
                    "model": config["WANDB_INFERENCE_MODEL"],
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Inference returned an empty text response.")
            return content

        @weave.op()
        def agent_loop(task: str, rounds: int) -> dict:
            return run_loop(task, complete, rounds)

        try:
            result = agent_loop(args.task, args.rounds)
        except httpx.HTTPStatusError as exc:
            parser.exit(
                1,
                f"W&B Inference returned HTTP {exc.response.status_code}. "
                "Check your key, credits, team, and model access.\n",
            )
        except httpx.RequestError:
            parser.exit(1, "Could not reach W&B Inference within the request timeout.\n")
        except (ValueError, KeyError, IndexError):
            parser.exit(1, "W&B Inference returned an unexpected or empty response.\n")

    print(json.dumps(result, indent=2))
    print(f"Weave project: https://wandb.ai/{project}/weave")


if __name__ == "__main__":
    main()
