from click.testing import CliRunner

from inventory_pipeline.cli import cli


def test_ingest_fixture_mode_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE_MODE", "fixture")
    monkeypatch.setenv("RAW_STORAGE_BACKEND", "local")
    monkeypatch.setenv("RAW_DATA_PATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["ingest", "--source-mode", "fixture", "--backfill-days", "1"])

    assert result.exit_code == 0, result.output
    assert "Ingestion complete" in result.output


def test_load_snowflake_without_credentials_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_STORAGE_BACKEND", "local")
    monkeypatch.setenv("RAW_DATA_PATH", str(tmp_path))
    monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
    monkeypatch.delenv("SNOWFLAKE_USER", raising=False)
    monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["load-snowflake"])

    assert result.exit_code != 0
    assert "Cannot load to Snowflake" in result.output


def test_metrics_command_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setenv("RAW_STORAGE_BACKEND", "local")
    monkeypatch.setenv("RAW_DATA_PATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    ingest_result = runner.invoke(
        cli, ["ingest", "--source-mode", "fixture", "--backfill-days", "1"]
    )
    assert ingest_result.exit_code == 0, ingest_result.output

    output_path = tmp_path / "project_metrics.md"
    metrics_result = runner.invoke(cli, ["metrics", "--output", str(output_path)])
    assert metrics_result.exit_code == 0, metrics_result.output
    assert "Project Metrics" in metrics_result.output
    assert output_path.exists()
