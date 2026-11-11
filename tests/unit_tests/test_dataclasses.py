"""Test dataclasses and associated methods
"""

from pathlib import Path
import arrow

from plandev_cli.schemas.api import ApiActivityPlanRead
from plandev_cli.schemas.client import Activity, ActivityPlanCreate, ActivityPlanRead
import json
import pytest

INPUTS_DIRECTORY = Path(__file__).parent.joinpath("files", "inputs")


def test_get_activity_start_time():
    with open(INPUTS_DIRECTORY.joinpath("get_activity_start_time.json"), "r") as fid:
        plan: ActivityPlanRead = ActivityPlanRead.from_json(fid.read())

    # Activity anchored to plan start
    assert plan.get_activity_start_time(2) == arrow.get("2030-01-01T02:00:00+00:00")

    # Activity anchored to plan end
    assert plan.get_activity_start_time(5) == arrow.get("2030-01-01T06:00:00+00:00")

    # 1-long chain of valid anchoring
    assert plan.get_activity_start_time(1) == arrow.get("2030-01-01T01:00:00+00:00")

    # 2-long chain of valid anchoring
    assert plan.get_activity_start_time(4) == arrow.get("2030-01-01T07:00:00+00:00")

    # Invalid: references anchor to activity end
    with pytest.raises(ValueError):
        plan.get_activity_start_time(3)

    # Invalid: anchor doesn't exist
    with pytest.raises(ValueError):
        plan.get_activity_start_time(6)

    # Pass activity instance instead of ID
    assert plan.get_activity_start_time(plan.activities[1]) == arrow.get("2030-01-01T02:00:00+00:00")


def test_plan_serializes_as_transfer_v3():
    with open(INPUTS_DIRECTORY.joinpath("get_activity_start_time.json"), "r") as fid:
        plan: ActivityPlanRead = ActivityPlanRead.from_json(fid.read())

    # end_time is derived, not serialized; sim_id is client-side only
    assert plan.end_time == arrow.get("2030-01-01T12:00:00+00:00")
    plan.sim_id = 7
    serialized = json.loads(plan.to_json())
    assert serialized["version"] == "3"
    assert serialized["duration"] == "12:00:00"
    assert "end_time" not in serialized and "sim_id" not in serialized
    assert serialized["activities"][0]["start_offset"] == "-01:00:00"

    # Round trip
    plan.sim_id = None
    assert ActivityPlanRead.from_json(json.dumps(serialized)) == plan

def test_plan_export_defaults_empty_activity_arguments_to_object():
    plan = ActivityPlanCreate(
        name="test plan",
        start_time="2030-01-01T00:00:00+00:00",
        duration="01:00:00",
        activities=[Activity(id=1, type="TestActivity", start_offset="00:00:00")],
    )

    assert json.loads(plan.to_json())["activities"][0]["arguments"] == {}

def test_plan_export_includes_simulation_template_arguments():
    api_plan = ApiActivityPlanRead.from_dict({
        "id": 1,
        "model_id": 1,
        "name": "plan with simulation template",
        "start_time": "2030-01-01T00:00:00+00:00",
        "duration": "01:00:00",
        "activity_directives": [],
        "simulations": [{
            "id": 1,
            "template": {
                "arguments": {"template_only": 100, "overridden": 2},
            },
            "arguments": {"overridden": 9, "plan_only": 7},
        }],
    })

    plan = ActivityPlanRead.from_api_read(api_plan)
    exported = json.loads(plan.to_json())

    # export must retain template values while giving plan overrides precedence.
    assert exported["simulation_arguments"] == {
        "template_only": 100,
        "overridden": 9,
        "plan_only": 7,
    }

def test_old_plan_format_is_rejected():
    with pytest.raises(TypeError):
        ActivityPlanRead.from_json(
            '{"name": "old", "start_time": "2030-01-01T00:00:00+00:00", "end_time": "2030-01-02T00:00:00+00:00",'
            ' "id": 1, "model_id": 1, "sim_id": 1, "activities": []}'
        )
