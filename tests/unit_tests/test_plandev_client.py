from pathlib import Path
from typing import Dict, List
import json
import re

import pytest

from plandev_cli.plandev_client import PlanDevClient
from plandev_cli.plandev_host import PlanDevHost
from plandev_cli.schemas.client import Activity
from plandev_cli.schemas.api import ApiActivityPlanRead
from plandev_cli.schemas.client import ActivityPlanRead
from plandev_cli.schemas.client import ActivityPlanCreate
from plandev_cli.schemas.client import ResourceType

BLANK_LINE_REGEX = r"^\s*$"
EXPECTED_RESULTS_DIRECTORY = Path(__file__).parent.joinpath("files", "expected_results")
INPUTS_DIRECTORY = Path(__file__).parent.joinpath("files", "inputs")


def _preprocess_query(q) -> str:
    lines: List[str] = q.split('\n')
    lines = [ln.strip() for ln in lines if not re.match(BLANK_LINE_REGEX, ln)]
    return ' '.join(lines)


class MockPlanDevHost(PlanDevHost):
    """
    Mock PlanDev host listens for test queries and returns a mocked response.

    Responses are stored in ./files/mock_responses. Each JSON file should 
    contain a list of entries, each with two objects called "request" and 
    "response". The former should be the JSON data for a GraphQL query. The 
    response should be the JSON expected to be returned by 
    `PlanDevHost.post_to_graphql()`.

    [
        {
            "request": {
                "query": query, 
                "variables": variables
            },
            "response": {<populate>}
        },
        ...
    ]

    Pass the name of the mock query file to the constructor.
    """

    MOCK_QUERIES_DIRECTORY = Path(
        __file__).parent.joinpath('files', 'mock_responses')

    def __init__(self, mock_query_name: str) -> None:
        mock_query_fn = self.MOCK_QUERIES_DIRECTORY.joinpath(
            f"{mock_query_name}.json")
        with open(mock_query_fn, 'r') as fid:
            self.mock_data: List = json.load(fid)

    def post_to_graphql(self, query: str, **kwargs) -> Dict:

        # Get the next transaction being mocked
        mock_transaction = self.mock_data.pop(0)

        # Check that queries match, excepting whitespace mismatches
        assert _preprocess_query(query) == _preprocess_query(
            mock_transaction["request"]["query"])

        # Check that variables match
        assert kwargs == mock_transaction["request"]["variables"]

        return mock_transaction["response"]

    def post_to_gateway_import_plan(self, form: Dict, file_contents: bytes) -> Dict:
        mock_transaction = self.mock_data.pop(0)
        assert form == mock_transaction["request"]["form"]
        assert json.loads(file_contents) == mock_transaction["request"]["file"]
        return mock_transaction["response"]


def test_list_all_activity_plans():
    plandev_host = MockPlanDevHost('list_all_activity_plans')
    client = PlanDevClient(plandev_host)

    expected = json.loads("""
    [
        {
            "id": 1,
            "name": "plan--1",
            "model_id": 1,
            "start_time": "2025-01-01T00:00:00+00:00",
            "duration": "48:00:00",
            "simulations": [
                {
                    "id": 1,
                    "arguments": {}
                }
            ],
            "tags": []
        },
        {
            "id": 2,
            "name": "plan--2",
            "model_id": 2,
            "start_time": "2025-01-01T00:00:00+00:00",
            "duration": "48:00:00",
            "simulations": [
                {
                    "id": 2,
                    "arguments": {}
                }
            ],
            "tags": [
                {
                    "tag": {
                        "id": 1,
                        "name": "Test",
                        "color": "#ffffff"
                    }
                }
            ]
        }
    ]""")
    expected = [ActivityPlanRead.from_api_read(
        ApiActivityPlanRead.from_dict(e)
    ) for e in expected]
    assert client.list_all_activity_plans() == expected


def test_create_activity():
    plandev_host = MockPlanDevHost('create_activity')
    client = PlanDevClient(plandev_host)

    activity = Activity.from_dict(
        {
            "id": 1,
            "type": "NoOp",
            "start_offset": "00:00:00",
            "arguments": {"aParameter": "2030-001T00:00:00Z"},
            "name": "My Activity",
            "metadata": {},
            "anchor_id": None,
            "anchored_to_start": True,
        }
    )

    res = client.create_activity(activity, 1)

    assert res == 15


def test_update_activity():
    plandev_host = MockPlanDevHost("update_activity")
    client = PlanDevClient(plandev_host)

    activity = Activity.from_dict(
        {
            "type": "NoOp",
            "start_offset": "00:00:00",
            "arguments": {"aParameter": "2030-001T00:00:00Z"},
            "name": "My Activity",
        }
    )

    res = client.update_activity(15, activity, 1)

    assert res == 15


def test_get_resource_samples():

    # CASE 1: Get all states
    plandev_host = MockPlanDevHost('get_resource_samples_1')
    client = PlanDevClient(plandev_host)

    with open(EXPECTED_RESULTS_DIRECTORY.joinpath('get_resource_samples_1.json'), 'r') as fid:
        expected = json.load(fid)

    res = client.get_resource_samples(1)
    assert res == expected

    # CASE 2: Get only speicifc states
    plandev_host = MockPlanDevHost('get_resource_samples_2')
    client = PlanDevClient(plandev_host)

    with open(EXPECTED_RESULTS_DIRECTORY.joinpath('get_resource_samples_2.json'), 'r') as fid:
        expected = json.load(fid)

    res = client.get_resource_samples(1, ["hardwareState"])
    assert res == expected


def test_get_activity_plan_by_id():
    plandev_host = MockPlanDevHost("get_activity_plan_by_id")
    client = PlanDevClient(plandev_host)

    with open(
        EXPECTED_RESULTS_DIRECTORY.joinpath("get_activity_plan_by_id.json"), "r"
    ) as fid:
        expected = json.load(fid)

    res = client.get_activity_plan_by_id(1).to_dict()
    assert res == expected


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("plandev_cli.plandev_client.time.sleep", lambda _: None)


@pytest.mark.parametrize(["case_name"], [("create_activity_plan_1",), ("create_activity_plan_2",)])
def test_create_activity_plan(case_name: str, no_sleep):
    plandev_host = MockPlanDevHost(case_name)
    client = PlanDevClient(plandev_host)

    with open(INPUTS_DIRECTORY.joinpath(f"{case_name}.json"), "r") as fid:
        input_plan = ActivityPlanCreate.from_plan_read(ActivityPlanRead.from_json(fid.read()))

    res = client.create_activity_plan(7, input_plan)

    # Expected plan ID from mock response is 456
    assert res == 456
    assert plandev_host.mock_data == []


def test_import_plan_embedded_model(no_sleep):
    """A plan embedding its model needs no model ID, and the plan bounds come from the file"""
    plandev_host = MockPlanDevHost("import_plan_embedded")
    client = PlanDevClient(plandev_host)

    with open(MockPlanDevHost.MOCK_QUERIES_DIRECTORY.joinpath("import_plan_embedded.json")) as fid:
        plan = json.load(fid)[0]["request"]["file"]

    assert client.import_plan(plan) == 456
    assert plandev_host.mock_data == []


def test_import_plan_failed(no_sleep):
    plandev_host = MockPlanDevHost("import_plan_failed")
    client = PlanDevClient(plandev_host)

    with open(MockPlanDevHost.MOCK_QUERIES_DIRECTORY.joinpath("import_plan_failed.json")) as fid:
        plan = json.load(fid)[0]["request"]["file"]

    with pytest.raises(RuntimeError, match="Import of plan 456 failed.*Activity type NoOp not found"):
        client.import_plan(plan, model_id=7)


def test_import_plan_requires_model_id():
    client = PlanDevClient(None)
    plan = {"version": "3", "name": "no-model", "start_time": "2030-01-01T00:00:00+00:00", "duration": "01:00:00"}
    with pytest.raises(ValueError, match="model_id is required"):
        client.import_plan(plan)


def test_create_activity_plan_assigns_missing_activity_ids(no_sleep):
    """Activities built in Python may have no ID; they are numbered around any IDs already used"""
    class CapturingHost(MockPlanDevHost):
        def post_to_gateway_import_plan(self, form, file_contents):
            self.imported = json.loads(file_contents)
            return {"plan_id": 1, "model_id": 7, "plan_import_request_id": 2}

        def post_to_graphql(self, query, **kwargs):
            return {"status": "complete", "reason": None}

    host = CapturingHost("create_activity_plan_1")
    plan = ActivityPlanCreate(
        name="p", start_time="2030-01-01T00:00:00+00:00", duration="01:00:00",
        activities=[Activity(type="A", start_offset="00:00:00"), Activity(type="B", start_offset="00:10:00", id=1)],
    )
    PlanDevClient(host).create_activity_plan(7, plan)

    assert [a["id"] for a in host.imported["activities"]] == [2, 1]
    assert plan.activities[0].id is None  # input is untouched


def test_get_resource_types():
    plandev_host = MockPlanDevHost("get_resource_types")
    client = PlanDevClient(plandev_host)

    expected = [
        ResourceType("/imager/dataRate", {"type": "real"}),
        ResourceType(
            "/imager/hardwareState",
            {
                "type": "variant",
                "variants": [
                    {"key": "OFF", "label": "OFF"},
                    {"key": "ON", "label": "ON"},
                ],
            },
        ),
        ResourceType(
            "/data/dataVolume",
            {
                "items": {"initial": {"type": "real"}, "rate": {"type": "real"}},
                "type": "struct",
            },
        ),
        ResourceType(
            "/data/arbitrarilyComplex",
            {
                "items": {
                    "items": {
                        "stringProperty": {"type": "string"},
                        "enumProperty": {
                            "type": "variant",
                            "variants": [
                                {"key": "A", "label": "A"},
                                {"key": "B", "label": "B"},
                            ],
                        },
                        "intProperty": {"type": "int"},
                        "booleanProperty": {"type": "boolean"},
                    },
                    "type": "struct",
                },
                "type": "series",
            },
        ),
    ]

    res = client.get_resource_types(1)
    assert res == expected

def test_upload_directive_metadata():
    plandev_host = MockPlanDevHost("upload_directive_metadata_schemas")
    client = PlanDevClient(plandev_host)

    with open(EXPECTED_RESULTS_DIRECTORY.joinpath('upload_directive_metadata_schemas.json'), 'r') as fid:
        expected = json.load(fid)

    schema_data = json.loads("""
    [
        { "key": "STRING_EXAMPLE", "schema": { "type": "string" } },
        { "key": "LONG_STRING_EXAMPLE", "schema": { "type": "long_string" } },
        {
        "key": "ENUM_EXAMPLE",
        "schema": { "enumerates": ["A", "B", "C"], "type": "enum" }
        }
    ]
    """)

    res = client.add_directive_metadata_schemas(schema_data)
    assert res == expected
