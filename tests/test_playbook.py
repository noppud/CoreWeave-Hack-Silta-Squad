"""Tests for versioned planning playbook (silta/playbook.py).

Per §11 item 12: Applicable ACTIVE lessons reach planner context; irrelevant,
merely-proposed or contradictory lessons do not.
"""

import pytest

from silta.domain import Feature, FeatureKind, PartSpec, ShopProfile, Tool, ToolKind, Units
from silta.playbook import (
    ActivationScope,
    ApplicabilityPredicate,
    LessonStatus,
    SourceKind,
    activate_lesson,
    create_playbook,
    load_lesson,
    load_playbook,
    persist_lesson,
    persist_playbook,
    propose_lesson,
    select_applicable,
    validate_lesson,
)
from silta.storage import LocalStorage


@pytest.fixture
def temp_storage(tmp_path):
    return LocalStorage(tmp_path / "playbook_test")


@pytest.fixture
def demo_spec():
    return PartSpec(
        spec_id="test-part",
        revision=1,
        units=Units.MM,
        material="aluminium",
        stock_x_mm=100.0,
        stock_y_mm=100.0,
        stock_z_mm=20.0,
        features=(
            Feature(
                feature_id="pocket1",
                kind=FeatureKind.POCKET_RECT_ROUNDED,
                x_min_mm=10.0,
                x_max_mm=50.0,
                y_min_mm=10.0,
                y_max_mm=50.0,
                corner_radius_mm=3.0,
                depth_mm=12.0,
            ),
        ),
    )


@pytest.fixture
def demo_shop():
    from silta.domain import OperationKind

    return ShopProfile(
        shop_id="test-shop",
        display_name="Test Shop",
        envelope_x_mm=400.0,
        envelope_y_mm=300.0,
        envelope_z_mm=250.0,
        max_feed_mm_min=4000.0,
        max_spindle_rpm=12000.0,
        tools=(
            Tool(
                tool_id="EM6",
                kind=ToolKind.END_MILL,
                diameter_mm=6.0,
                cutting_length_mm=18.0,
                stickout_mm=34.0,
                shank_diameter_mm=6.0,
                holder_diameter_mm=26.0,
                center_cutting=True,
                allowed_operations=(OperationKind.POCKET_RASTER,),
                feed_mm_min=700.0,
                spindle_rpm=6500.0,
            ),
        ),
        home_x_mm=0.0,
        home_y_mm=0.0,
        home_z_mm=25.0,
    )


def test_propose_lesson():
    """A lesson can be proposed with structured applicability."""
    applicability = ApplicabilityPredicate(
        feature_kinds=(FeatureKind.POCKET_RECT_ROUNDED,),
        requires_fixtures=True,
        min_depth_mm=10.0,
    )

    lesson = propose_lesson(
        instruction="Set clearance above fixture height plus margin",
        applicability=applicability,
        source_kind=SourceKind.HUMAN,
        lesson_id="lesson-fixture-clearance",
    )

    assert lesson.lesson_id == "lesson-fixture-clearance"
    assert lesson.revision == 1
    assert lesson.status == LessonStatus.PROPOSED
    assert lesson.applicability == applicability
    assert lesson.source_kind == SourceKind.HUMAN


def test_validate_and_activate_lesson():
    """A proposed lesson can be validated then activated."""
    applicability = ApplicabilityPredicate(requires_fixtures=True)
    lesson = propose_lesson(
        instruction="Test instruction",
        applicability=applicability,
        source_kind=SourceKind.HUMAN,
    )

    assert lesson.status == LessonStatus.PROPOSED

    validated = validate_lesson(lesson, validation_reference="test-validation-001")
    assert validated.status == LessonStatus.VALIDATED
    assert validated.validation_reference == "test-validation-001"

    activated = activate_lesson(validated)
    assert activated.status == LessonStatus.ACTIVE
    assert activated.activated_at is not None


def test_validate_only_proposed():
    """Only PROPOSED lessons can be validated."""
    applicability = ApplicabilityPredicate()
    lesson = propose_lesson("Test", applicability, SourceKind.HUMAN)
    validated = validate_lesson(lesson, "ref")

    with pytest.raises(ValueError, match="Can only validate PROPOSED"):
        validate_lesson(validated, "ref2")


def test_activate_only_validated():
    """Only VALIDATED lessons can be activated."""
    applicability = ApplicabilityPredicate()
    lesson = propose_lesson("Test", applicability, SourceKind.HUMAN)

    with pytest.raises(ValueError, match="Can only activate VALIDATED"):
        activate_lesson(lesson)


def test_applicability_matching_fixtures(demo_spec, demo_shop):
    """Applicability predicate matches based on fixtures."""
    # Requires fixtures, but shop has none
    pred_requires = ApplicabilityPredicate(requires_fixtures=True)
    assert not pred_requires.matches(demo_spec, demo_shop)

    # Add fixtures to shop
    from silta.domain import FixtureSolid

    shop_with_fixtures = demo_shop.model_copy(
        update={
            "fixtures": (
                FixtureSolid(
                    fixture_id="clamp1",
                    x_min_mm=0.0,
                    x_max_mm=10.0,
                    y_min_mm=0.0,
                    y_max_mm=10.0,
                    z_min_mm=0.0,
                    z_max_mm=10.0,
                ),
            )
        }
    )
    assert pred_requires.matches(demo_spec, shop_with_fixtures)


def test_applicability_matching_feature_kinds(demo_spec, demo_shop):
    """Applicability predicate matches based on feature kinds."""
    pred = ApplicabilityPredicate(feature_kinds=(FeatureKind.POCKET_RECT_ROUNDED,))
    assert pred.matches(demo_spec, demo_shop)

    pred_drill = ApplicabilityPredicate(feature_kinds=(FeatureKind.HOLE_BLIND,))
    assert not pred_drill.matches(demo_spec, demo_shop)


def test_applicability_matching_depth(demo_spec, demo_shop):
    """Applicability predicate matches based on feature depth."""
    # demo_spec has pocket with 12mm depth
    pred_shallow = ApplicabilityPredicate(max_depth_mm=10.0)
    assert not pred_shallow.matches(demo_spec, demo_shop)

    pred_deep = ApplicabilityPredicate(min_depth_mm=5.0, max_depth_mm=15.0)
    assert pred_deep.matches(demo_spec, demo_shop)


def test_select_applicable_only_active(demo_spec, demo_shop):
    """Only ACTIVE lessons are selected; proposed/validated are ignored."""
    pred = ApplicabilityPredicate()

    proposed = propose_lesson("Proposed lesson", pred, SourceKind.HUMAN, "lesson-1")
    validated = validate_lesson(
        propose_lesson("Validated lesson", pred, SourceKind.HUMAN, "lesson-2"), "ref"
    )
    active = activate_lesson(
        validate_lesson(propose_lesson("Active lesson", pred, SourceKind.HUMAN, "lesson-3"), "ref")
    )

    lessons = [proposed, validated, active]
    selected, versions = select_applicable(lessons, demo_spec, demo_shop)

    assert len(selected) == 1
    assert selected[0].lesson_id == "lesson-3"
    assert versions == ["lesson-3:r1"]


def test_select_applicable_respects_bounds(demo_spec, demo_shop):
    """Selection respects max_lessons and max_tokens bounds."""
    pred = ApplicabilityPredicate()
    lessons = []
    for i in range(10):
        lesson = propose_lesson(f"Lesson {i} instruction", pred, SourceKind.HUMAN, f"lesson-{i}")
        lesson = validate_lesson(lesson, f"ref-{i}")
        lesson = activate_lesson(lesson)
        lessons.append(lesson)

    # Max 3 lessons
    selected, _ = select_applicable(lessons, demo_spec, demo_shop, max_lessons=3)
    assert len(selected) == 3

    # Max tokens (very restrictive)
    selected, _ = select_applicable(lessons, demo_spec, demo_shop, max_tokens=50)
    assert len(selected) < 10


def test_select_applicable_filters_irrelevant(demo_spec, demo_shop):
    """Irrelevant lessons are not selected."""
    # Lesson that requires fixtures
    pred_fixtures = ApplicabilityPredicate(requires_fixtures=True)
    lesson_fixtures = activate_lesson(
        validate_lesson(
            propose_lesson("Fixture lesson", pred_fixtures, SourceKind.HUMAN, "lesson-fix"), "ref"
        )
    )

    # Lesson that requires holes
    pred_holes = ApplicabilityPredicate(feature_kinds=(FeatureKind.HOLE_BLIND,))
    lesson_holes = activate_lesson(
        validate_lesson(
            propose_lesson("Hole lesson", pred_holes, SourceKind.HUMAN, "lesson-hole"), "ref"
        )
    )

    # Lesson that's always applicable
    pred_any = ApplicabilityPredicate()
    lesson_any = activate_lesson(
        validate_lesson(
            propose_lesson("Any lesson", pred_any, SourceKind.HUMAN, "lesson-any"), "ref"
        )
    )

    lessons = [lesson_fixtures, lesson_holes, lesson_any]
    selected, versions = select_applicable(lessons, demo_spec, demo_shop)

    # Only lesson_any should be selected (no fixtures, no holes in demo_spec/demo_shop)
    assert len(selected) == 1
    assert selected[0].lesson_id == "lesson-any"


def test_create_playbook():
    """A playbook can be created from active lessons."""
    pred = ApplicabilityPredicate()
    lesson1 = activate_lesson(
        validate_lesson(propose_lesson("Lesson 1", pred, SourceKind.HUMAN, "lesson-1"), "ref1")
    )
    lesson2 = activate_lesson(
        validate_lesson(propose_lesson("Lesson 2", pred, SourceKind.HUMAN, "lesson-2"), "ref2")
    )

    playbook = create_playbook([lesson1, lesson2], ActivationScope.TEAM_DEFAULT)

    assert playbook.activation_scope == ActivationScope.TEAM_DEFAULT
    assert len(playbook.lesson_versions) == 2
    assert "lesson-1:r1" in playbook.lesson_versions
    assert "lesson-2:r1" in playbook.lesson_versions
    assert playbook.playbook_version.startswith("playbook-")


def test_persist_and_load_lesson(temp_storage):
    """Lessons can be persisted and loaded from storage."""
    pred = ApplicabilityPredicate(requires_fixtures=True)
    lesson = propose_lesson("Test persistence", pred, SourceKind.HUMAN, lesson_id="persist-test")

    # Persist
    key = persist_lesson(lesson, temp_storage)
    assert key.endswith(".json")

    # Load
    loaded = load_lesson("persist-test", 1, temp_storage)
    assert loaded.lesson_id == lesson.lesson_id
    assert loaded.instruction == lesson.instruction
    assert loaded.applicability == lesson.applicability


def test_persist_and_load_playbook(temp_storage):
    """Playbooks can be persisted and loaded from storage."""
    pred = ApplicabilityPredicate()
    lesson = activate_lesson(
        validate_lesson(propose_lesson("Test", pred, SourceKind.HUMAN, "lesson-pb"), "ref")
    )

    playbook = create_playbook([lesson], ActivationScope.PUBLIC_SESSION)

    # Persist
    key = persist_playbook(playbook, temp_storage)
    assert key.endswith(".json")

    # Load
    loaded = load_playbook(playbook.playbook_version, temp_storage)
    assert loaded.playbook_version == playbook.playbook_version
    assert loaded.lesson_versions == playbook.lesson_versions
    assert loaded.activation_scope == playbook.activation_scope


def test_lesson_version_string():
    """Lesson version string is lesson_id:rN."""
    pred = ApplicabilityPredicate()
    lesson = propose_lesson("Test", pred, SourceKind.HUMAN, lesson_id="test-123")
    assert lesson.lesson_version == "test-123:r1"


def test_playbook_with_parent_version():
    """Playbook can reference a parent version."""
    pred = ApplicabilityPredicate()
    lesson = activate_lesson(
        validate_lesson(propose_lesson("Test", pred, SourceKind.HUMAN, "lesson"), "ref")
    )

    playbook_v1 = create_playbook([lesson], ActivationScope.TEAM_DEFAULT)
    playbook_v2 = create_playbook(
        [lesson], ActivationScope.TEAM_DEFAULT, parent_version=playbook_v1.playbook_version
    )

    assert playbook_v2.parent_version == playbook_v1.playbook_version
