"""Inspect actual Fusion CAM strategy inputs without adding operations."""


def _requested(payload):
    strategies = payload.get("strategies", [])
    index = payload.get("setup_index", 0)
    if type(index) is not int or index < 0:
        raise ValueError("setup_index must be a nonnegative integer")
    if not isinstance(strategies, list) or any(
        not isinstance(name, str) or not name.strip() for name in strategies
    ):
        raise ValueError("strategies must be a list of strategy IDs")
    if len(set(strategies)) != len(strategies):
        raise ValueError("Duplicate strategy IDs")
    return index, strategies


def describe(app, payload):
    import adsk.cam

    index, requested = _requested(payload)
    if app.activeDocument is None:
        raise RuntimeError("No active CAM document")
    cam = adsk.cam.CAM.cast(app.activeDocument.products.itemByProductType("CAMProductType"))
    if cam is None or index >= cam.setups.count:
        raise RuntimeError("Requested CAM setup is unavailable")
    setup = cam.setups.item(index)
    owner = setup.attributes.itemByName("silta", "controller_setup")
    if owner is None or owner.value != "v1":
        raise RuntimeError("Catalog requires the controller-owned setup")
    operations = setup.operations
    before = operations.count
    compatible = [
        {"name": s.name, "title": s.title, "generation_allowed": s.isGenerationAllowed}
        for s in operations.compatibleStrategies
    ]
    names = {s["name"] for s in compatible}
    descriptions = {}
    for strategy in requested:
        if strategy not in names:
            descriptions[strategy] = {"error": "Strategy is not compatible with this setup"}
            continue
        try:
            operation_input = operations.createInput(strategy)
            if operation_input is None:
                raise RuntimeError("Fusion did not create the transient strategy input")
            rows = []
            for parameter in operation_input.parameters:
                row = {"name": parameter.name, "title": parameter.title}
                try:
                    value = parameter.value
                    row.update(
                        expression=parameter.expression,
                        value_type=value.objectType,
                        enabled=parameter.isEnabled,
                        editable=parameter.isEditable,
                        deprecated=parameter.isDeprecated,
                    )
                    choice = adsk.cam.ChoiceParameterValue.cast(value)
                    if choice is not None:
                        ok, labels, values = choice.getChoices()
                        row["choices_available"] = ok
                        row["choices"] = [
                            {"title": title, "value": item}
                            for title, item in zip(labels, values, strict=True)
                        ]
                        row["selected_value"] = choice.value
                except Exception as error:
                    row["read_error"] = str(error)
                rows.append(row)
            descriptions[strategy] = {"parameters": rows}
        except Exception as error:
            descriptions[strategy] = {"error": str(error)}
    if operations.count != before:
        raise RuntimeError("Operation count changed during read-only CAM inspection")
    return {
        "setup_index": index,
        "setup_name": setup.name,
        "compatible_strategies": compatible,
        "strategies": descriptions,
        "operation_count": before,
        "defaults_note": "Transient inputs use current Fusion user defaults; no tool or "
        "geometry was assigned. Enabled states can change with other values.",
    }
