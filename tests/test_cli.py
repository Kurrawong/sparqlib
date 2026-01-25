from pathlib import Path

import pytest
from typer.testing import CliRunner

from sparqlkit.cli import app

runner = CliRunner()

VALID_QUERY = "SELECT ?s WHERE { ?s ?p ?o }"
FORMATTED_QUERY = """\
SELECT ?s
WHERE {
  ?s ?p ?o
}"""
INVALID_QUERY = "SELECT ?s WHERE { ?s ?p"


@pytest.fixture
def valid_file(tmp_path: Path) -> Path:
    file = tmp_path / "valid.rq"
    file.write_text(VALID_QUERY, encoding="utf-8")
    return file


@pytest.fixture
def formatted_file(tmp_path: Path) -> Path:
    file = tmp_path / "formatted.rq"
    file.write_text(FORMATTED_QUERY, encoding="utf-8")
    return file


@pytest.fixture
def invalid_file(tmp_path: Path) -> Path:
    file = tmp_path / "invalid.rq"
    file.write_text(INVALID_QUERY, encoding="utf-8")
    return file


@pytest.fixture
def valid_dir(tmp_path: Path) -> Path:
    (tmp_path / "a.rq").write_text(VALID_QUERY, encoding="utf-8")
    (tmp_path / "b.sparql").write_text(VALID_QUERY, encoding="utf-8")
    return tmp_path


@pytest.fixture
def formatted_dir(tmp_path: Path) -> Path:
    (tmp_path / "a.rq").write_text(FORMATTED_QUERY, encoding="utf-8")
    (tmp_path / "b.sparql").write_text(FORMATTED_QUERY, encoding="utf-8")
    return tmp_path


def test_format_valid_file(valid_file: Path):
    result = runner.invoke(app, ["format", str(valid_file)])
    assert result.exit_code == 0
    assert "Formatted" in result.stdout


def test_format_invalid_file(invalid_file: Path):
    result = runner.invoke(app, ["format", str(invalid_file)])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_format_directory(valid_dir: Path):
    result = runner.invoke(app, ["format", str(valid_dir)])
    assert result.exit_code == 0
    assert result.stdout.count("Formatted") == 2


def test_format_nonexistent_path(tmp_path: Path):
    result = runner.invoke(app, ["format", str(tmp_path / "nonexistent")])
    assert result.exit_code == 1
    assert "No SPARQL files found" in result.output


def test_format_check_formatted_file(formatted_file: Path):
    result = runner.invoke(app, ["format", "--check", str(formatted_file)])
    assert result.exit_code == 0
    assert "OK" in result.stdout


def test_format_check_unformatted_file(valid_file: Path):
    result = runner.invoke(app, ["format", "--check", str(valid_file)])
    assert result.exit_code == 1
    assert "Would reformat" in result.output


def test_format_check_invalid_file(invalid_file: Path):
    result = runner.invoke(app, ["format", "--check", str(invalid_file)])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_format_check_formatted_directory(formatted_dir: Path):
    result = runner.invoke(app, ["format", "--check", str(formatted_dir)])
    assert result.exit_code == 0
    assert "All 2 file(s) OK" in result.stdout


def test_format_check_unformatted_directory(valid_dir: Path):
    result = runner.invoke(app, ["format", "--check", str(valid_dir)])
    assert result.exit_code == 1
    assert "Would reformat" in result.output


def test_format_check_nonexistent_path(tmp_path: Path):
    result = runner.invoke(app, ["format", "--check", str(tmp_path / "nonexistent")])
    assert result.exit_code == 1
    assert "No SPARQL files found" in result.output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert "Commands" in result.output


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "format" in result.output


def test_short_help_flag():
    result = runner.invoke(app, ["-h"])
    assert result.exit_code == 0
    assert "format" in result.output


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() != ""
