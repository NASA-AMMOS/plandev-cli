"""Test the `plans upload` command against a mocked client"""

import json

import pytest
from typer.testing import CliRunner

from plandev_cli.app import app
from plandev_cli.commands.command_context import CommandContext

RUNNER = CliRunner()


class FakeClient:
    def __init__(self):
        self.calls = []

    def import_plan(self, plan, model_id=None, name=None):
        self.calls.append((plan, model_id, name))
        return 42


@pytest.fixture
def client(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(CommandContext, "get_client", classmethod(lambda cls: fake))
    return fake


def _write(tmp_path, plan):
    path = tmp_path.joinpath("plan.json")
    path.write_text(json.dumps(plan))
    return str(path)


PLAN = {"version": "3", "name": "my-plan", "start_time": "2030-01-01T00:00:00+00:00", "duration": "24:00:00"}


def test_upload_with_model_id(client, tmp_path):
    result = RUNNER.invoke(app, ["plans", "upload", "-i", _write(tmp_path, PLAN), "--model-id", "3"])
    assert result.exit_code == 0, result.stdout
    assert "Created plan ID: 42" in result.stdout
    assert client.calls == [(PLAN, 3, "my-plan")]


def test_upload_prompts_for_missing_model_id(client, tmp_path):
    result = RUNNER.invoke(app, ["plans", "upload", "-i", _write(tmp_path, PLAN)], input="3\n")
    assert result.exit_code == 0, result.stdout
    assert client.calls[0][1] == 3


def test_upload_embedded_model_needs_no_model_id(client, tmp_path):
    plan = {**PLAN, "model": {"activity_types": [], "resource_types": []}}
    result = RUNNER.invoke(app, ["plans", "upload", "-i", _write(tmp_path, plan)])
    assert result.exit_code == 0, result.stdout
    assert client.calls == [(plan, None, "my-plan")]


def test_upload_time_tag(client, tmp_path):
    result = RUNNER.invoke(app, ["plans", "upload", "-i", _write(tmp_path, PLAN), "-m", "3", "--time-tag"])
    assert result.exit_code == 0, result.stdout
    assert client.calls[0][2].startswith("my-plan20")
