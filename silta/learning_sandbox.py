"""W&B Sandbox regression gate for trusted, bounded learning templates.

Sandbox files are disposable. Only the host persists returned validation evidence.
No credentials or arbitrary model-written code are sent into the sandbox.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

# Independent fixed labels: collision, safe, exact boundary, absent fixture,
# below boundary, and an intentionally invalid negative clearance.
VALIDATION_SCRIPT = """
import json, sys
candidate = json.loads(sys.argv[1])
assert candidate == {"template": "fixture_clearance_v1"}
cases = [
    ("collision", 5, 12, 3, True, False),
    ("safe", 20, 12, 3, True, True),
    ("boundary", 15, 12, 3, True, True),
    ("below_boundary", 14.99, 12, 3, True, False),
    ("no_fixture", 5, 12, 3, False, True),
    ("invalid_clearance", -1, 0, 0, False, False),
]
results = []
for name, clearance, top, margin, fixtures, expected in cases:
    actual = clearance > 0 and (not fixtures or clearance >= top + margin)
    results.append({"case": name, "expected": expected, "actual": actual,
                    "passed": actual == expected})
print(json.dumps({"passed": all(r["passed"] for r in results), "cases": results}))
"""


class WandbLessonValidator:
    def validate(self, lesson: dict) -> dict:
        report = {
            "report_id": "validation-" + uuid.uuid4().hex[:16],
            "lesson_id": lesson["lesson_id"],
            "backend": "wandb_sandbox",
            "template": "fixture_clearance_v1",
            "status": "unavailable",
            "created_at": datetime.now(UTC).isoformat(),
            "scope": "Planning advice only; does not promote or replace machining checks.",
        }
        try:
            from wandb.sandbox import Sandbox

            with Sandbox.run(
                max_lifetime_seconds=60,
                request_timeout_seconds=10,
                poll_retry_budget_seconds=10,
                tags=["silta", "lesson-validation"],
            ) as sandbox:
                report["sandbox_id"] = str(sandbox.sandbox_id)
                result = sandbox.exec(
                    [
                        "python",
                        "-c",
                        VALIDATION_SCRIPT,
                        json.dumps({"template": "fixture_clearance_v1"}),
                    ],
                    timeout_seconds=15,
                ).result()
                report["exit_code"] = result.returncode
                if result.returncode != 0:
                    report["status"] = "failed"
                else:
                    evidence = json.loads(result.stdout)
                    report["cases"] = evidence["cases"]
                    report["status"] = "passed" if evidence["passed"] else "failed"
        except Exception as exc:
            # An entitlement/transport failure is not a successful validation, and
            # SDK exception text can include URLs or auth details. Keep only its type.
            report["error_type"] = type(exc).__name__
        return report
