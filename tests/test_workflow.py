from pathlib import Path

import yaml


def test_workflow_schedule_permissions_and_secret_isolation():
    workflow = yaml.safe_load((Path(__file__).parents[1] / ".github/workflows/jobs.yml").read_text())
    assert workflow["on"]["schedule"] == [{"cron": "0 */2 * * *"}]
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] is False
    scan = workflow["jobs"]["scan"]
    assert scan["needs"] == "test"
    assert scan["if"] == "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
    assert scan["timeout-minutes"] <= 30
    sync = scan["steps"][-1]
    assert set(sync["env"]) == {"GOOGLE_SERVICE_ACCOUNT_JSON", "SPREADSHEET_ID", "DISCORD_WEBHOOK_URL"}
    assert all("secrets." in value for value in sync["env"].values())
