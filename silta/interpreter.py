"""Drawing and text -> an unconfirmed specification proposal.

Nothing here is allowed to become a confirmed `PartSpec` on its own. Unknown
values stay unknown and are returned as `unresolved_fields` so the operator
resolves them explicitly. A confidence label is a label, not a calibrated
probability.
"""

from __future__ import annotations

import base64
import json
import re
import uuid
from dataclasses import dataclass

from silta.domain import (
    DrillTipConvention,
    Feature,
    FeatureKind,
    SourceAsset,
    SpecProposal,
    Units,
)
from silta.fixtures import DEMO_SPEC

_DIM3 = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:mm|millimet\w*)?\s*[x×*]\s*(\d+(?:\.\d+)?)\s*(?:mm|millimet\w*)?"
    r"\s*[x×*]\s*(\d+(?:\.\d+)?)\s*(mm|millimet\w*|in|inch\w*|\"|')?",
    re.IGNORECASE,
)
_POCKET = re.compile(
    r"pocket[^.]*?x\s*=?\s*(\d+(?:\.\d+)?)\s*(?:to|\.\.\.?|-|…)\s*(\d+(?:\.\d+)?)"
    r"[^.]*?y\s*=?\s*(\d+(?:\.\d+)?)\s*(?:to|\.\.\.?|-|…)\s*(\d+(?:\.\d+)?)"
    r"[^.]*?depth\s*=?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE | re.DOTALL,
)
_RADIUS = re.compile(r"(?:corner\s+)?radius\s*=?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_HOLE = re.compile(
    r"\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)",
)
_HOLE_SPEC = re.compile(
    r"(?:diameter|dia|ø|d)\s*=?\s*(\d+(?:\.\d+)?)[^.]*?depth\s*=?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_MATERIAL = re.compile(
    r"\b(6061[- ]?T\d|7075[- ]?T\d|aluminium|aluminum|brass|mild steel|stainless|"
    r"304 stainless|delrin|acetal|abs|pom)\b",
    re.IGNORECASE,
)
_UNIT_WORDS = re.compile(r"\b(mm|millimet\w*|inch\w*|in\.|imperial|metric)\b", re.IGNORECASE)


@dataclass(frozen=True)
class InterpretRequest:
    message: str
    assets: tuple[SourceAsset, ...] = ()
    asset_bytes: dict[str, bytes] | None = None
    use_example: bool = False


def _units_from(text: str) -> tuple[Units, str | None]:
    match = _UNIT_WORDS.search(text)
    if not match:
        return Units.UNKNOWN, "No unit was stated anywhere in the request."
    word = match.group(1).lower()
    if word.startswith(("inch", "in.")) or word == "imperial":
        return Units.INCH, None
    return Units.MM, None


def example_proposal() -> SpecProposal:
    """The supplied dimensioned fixture-block example, fully resolved."""
    return SpecProposal(
        proposal_id=f"prop-{uuid.uuid4().hex[:10]}",
        spec_id=DEMO_SPEC.spec_id,
        revision=1,
        units=DEMO_SPEC.units,
        material=DEMO_SPEC.material,
        stock_x_mm=DEMO_SPEC.stock_x_mm,
        stock_y_mm=DEMO_SPEC.stock_y_mm,
        stock_z_mm=DEMO_SPEC.stock_z_mm,
        features=DEMO_SPEC.features,
        unresolved_fields=(),
        assumptions=(
            "Supplied demonstration drawing; dimensions are read directly from it.",
            "Blind-hole depth is the full-diameter cylindrical depth; the 118 degree "
            "drill point reaches 1.803 mm deeper.",
        ),
        evidence={
            "stock": "drawing title block",
            "pocket_1": "views A1-A3",
            "holes": "views B1-B4",
        },
        origin="example",
    )


def interpret_text(request: InterpretRequest) -> SpecProposal:
    """Deterministic extraction from typed text. Never invents a missing number."""
    text = request.message
    units, unit_note = _units_from(text)
    unresolved: list[str] = []
    assumptions: list[str] = []
    evidence: dict[str, str] = {}
    if units is Units.UNKNOWN:
        unresolved.append("units")
        if unit_note:
            assumptions.append(unit_note)

    stock = _DIM3.search(text)
    stock_x = stock_y = stock_z = None
    if stock:
        stock_x, stock_y, stock_z = (float(stock.group(i)) for i in (1, 2, 3))
        evidence["stock"] = f"typed: {stock.group(0).strip()}"
    else:
        unresolved.append("stock dimensions")

    material_match = _MATERIAL.search(text)
    material = material_match.group(0) if material_match else None
    if material is None:
        unresolved.append("material")
    else:
        evidence["material"] = f"typed: {material}"

    features: list[Feature] = []
    pocket = _POCKET.search(text)
    if pocket:
        radius_match = _RADIUS.search(text)
        if radius_match is None:
            unresolved.append("pocket corner radius")
        else:
            x0, x1, y0, y1, depth = (float(pocket.group(i)) for i in range(1, 6))
            try:
                features.append(
                    Feature(
                        feature_id="pocket_1",
                        kind=FeatureKind.POCKET_RECT_ROUNDED,
                        x_min_mm=min(x0, x1),
                        x_max_mm=max(x0, x1),
                        y_min_mm=min(y0, y1),
                        y_max_mm=max(y0, y1),
                        corner_radius_mm=float(radius_match.group(1)),
                        depth_mm=depth,
                        drawing_refs=("typed",),
                    )
                )
                evidence["pocket_1"] = f"typed: {pocket.group(0)[:80].strip()}"
            except ValueError as exc:
                unresolved.append(f"pocket ({exc})")

    hole_spec = _HOLE_SPEC.search(text)
    centres = _HOLE.findall(text)
    if centres and hole_spec:
        diameter, depth = float(hole_spec.group(1)), float(hole_spec.group(2))
        for index, (cx, cy) in enumerate(centres, start=1):
            try:
                features.append(
                    Feature(
                        feature_id=f"hole_{index}",
                        kind=FeatureKind.HOLE_BLIND,
                        center_x_mm=float(cx),
                        center_y_mm=float(cy),
                        diameter_mm=diameter,
                        depth_mm=depth,
                        drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                        drill_point_angle_deg=118.0,
                        drawing_refs=("typed",),
                    )
                )
            except ValueError as exc:
                unresolved.append(f"hole_{index} ({exc})")
        assumptions.append(
            "Blind-hole depth read as the full-diameter cylindrical depth with a "
            "118 degree drill point; confirm if the drawing means total tip depth."
        )
        evidence["holes"] = f"typed: {len(centres)} centres"
    elif centres or hole_spec:
        unresolved.append("hole diameter and depth")

    if not features:
        unresolved.append("at least one feature (pocket or hole)")

    return SpecProposal(
        proposal_id=f"prop-{uuid.uuid4().hex[:10]}",
        spec_id=f"spec-{uuid.uuid4().hex[:8]}",
        revision=1,
        units=units,
        material=material,
        stock_x_mm=stock_x,
        stock_y_mm=stock_y,
        stock_z_mm=stock_z,
        features=tuple(features),
        unresolved_fields=tuple(dict.fromkeys(unresolved)),
        assumptions=tuple(assumptions),
        evidence=evidence,
        origin="typed",
    )


VISION_SYSTEM = (
    "You read dimensioned engineering drawings of simple milled blocks. "
    "Return only values the drawing actually states. If a dimension, unit or material "
    "is absent, list it in unresolved_fields instead of guessing. Never infer a "
    "dimension from pixel measurement."
)

VISION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["units", "unresolved_fields", "features"],
    "properties": {
        "units": {"type": "string", "enum": ["mm", "inch", "unknown"]},
        "material": {"type": ["string", "null"]},
        "stock_x": {"type": ["number", "null"]},
        "stock_y": {"type": ["number", "null"]},
        "stock_z": {"type": ["number", "null"]},
        "unresolved_fields": {"type": "array", "items": {"type": "string"}},
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["feature_id", "kind", "depth"],
                "properties": {
                    "feature_id": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["pocket_rect_rounded", "hole_blind"],
                    },
                    "depth": {"type": "number"},
                    "x_min": {"type": ["number", "null"]},
                    "x_max": {"type": ["number", "null"]},
                    "y_min": {"type": ["number", "null"]},
                    "y_max": {"type": ["number", "null"]},
                    "corner_radius": {"type": ["number", "null"]},
                    "center_x": {"type": ["number", "null"]},
                    "center_y": {"type": ["number", "null"]},
                    "diameter": {"type": ["number", "null"]},
                },
            },
        },
    },
}


async def interpret_drawing(request: InterpretRequest, vision_provider) -> SpecProposal:
    """Vision route. Falls back to an explicit request for dimensions, never a guess."""
    image = next(
        (a for a in request.assets if a.mime in ("image/png", "image/jpeg")),
        None,
    )
    blob = (request.asset_bytes or {}).get(image.asset_id) if image else None
    if vision_provider is None or image is None or blob is None:
        proposal = interpret_text(request)
        note = (
            "No vision model is configured, so nothing was read from the image."
            if image is not None
            else "No drawing image was supplied."
        )
        return proposal.model_copy(
            update={
                "assumptions": (*proposal.assumptions, note),
                "unresolved_fields": tuple(
                    dict.fromkeys([*proposal.unresolved_fields, "dimensions from the drawing"])
                ),
            }
        )

    encoded = base64.b64encode(blob).decode("ascii")
    completion = await vision_provider.complete_json(
        system=VISION_SYSTEM,
        user=[
            {"type": "text", "text": request.message or "Read this drawing."},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image.mime};base64,{encoded}"},
            },
        ],
        schema=VISION_SCHEMA,
        max_tokens=2000,
        timeout_s=45.0,
    )
    payload = completion.parsed or json.loads(completion.text)
    return _proposal_from_payload(payload, completion)


def _proposal_from_payload(payload: dict, completion) -> SpecProposal:
    features: list[Feature] = []
    unresolved = list(payload.get("unresolved_fields") or [])
    for raw in payload.get("features") or []:
        try:
            if raw["kind"] == "pocket_rect_rounded":
                features.append(
                    Feature(
                        feature_id=raw["feature_id"],
                        kind=FeatureKind.POCKET_RECT_ROUNDED,
                        x_min_mm=raw["x_min"],
                        x_max_mm=raw["x_max"],
                        y_min_mm=raw["y_min"],
                        y_max_mm=raw["y_max"],
                        corner_radius_mm=raw["corner_radius"],
                        depth_mm=raw["depth"],
                        drawing_refs=("vision",),
                    )
                )
            else:
                features.append(
                    Feature(
                        feature_id=raw["feature_id"],
                        kind=FeatureKind.HOLE_BLIND,
                        center_x_mm=raw["center_x"],
                        center_y_mm=raw["center_y"],
                        diameter_mm=raw["diameter"],
                        depth_mm=raw["depth"],
                        drill_tip=DrillTipConvention.CYLINDRICAL_DEPTH,
                        drill_point_angle_deg=118.0,
                        drawing_refs=("vision",),
                    )
                )
        except (KeyError, TypeError, ValueError) as exc:
            unresolved.append(f"{raw.get('feature_id', 'feature')} ({exc})")
    return SpecProposal(
        proposal_id=f"prop-{uuid.uuid4().hex[:10]}",
        spec_id=f"spec-{uuid.uuid4().hex[:8]}",
        revision=1,
        units=Units(payload.get("units", "unknown")),
        material=payload.get("material"),
        stock_x_mm=payload.get("stock_x"),
        stock_y_mm=payload.get("stock_y"),
        stock_z_mm=payload.get("stock_z"),
        features=tuple(features),
        unresolved_fields=tuple(dict.fromkeys(unresolved)),
        assumptions=("Values were read from the drawing by a vision model and must be confirmed.",),
        evidence={"source": "vision model"},
        origin="vision",
        provider=completion.provider,
        model=completion.model,
    )


def clarification_message(proposal: SpecProposal) -> str:
    """One coherent clarification request, not a drip of questions."""
    if proposal.ready:
        return "Everything needed is present. Review the values and confirm the specification."
    lines = ["I need these before I can build the model:"]
    lines += [f"- {field}" for field in proposal.unresolved_fields]
    if proposal.assumptions:
        lines.append("")
        lines.append("Assumptions I am making, which you can correct:")
        lines += [f"- {note}" for note in proposal.assumptions]
    return "\n".join(lines)
