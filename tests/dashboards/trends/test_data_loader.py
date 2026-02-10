"""Tests for TrendsDataLoader class

Tests data loading, validation, and error handling for trends dashboard.
"""

import json
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from execution.dashboards.trends.data_loader import TrendsDataLoader


@pytest.fixture
def sample_quality_data():
    """Sample quality history JSON data"""
    return {
        "weeks": [
            {"projects": [{"open_bugs_count": 300}, {"open_bugs_count": 50}]},
            {"projects": [{"open_bugs_count": 280}, {"open_bugs_count": 45}]},
            {"projects": [{"open_bugs_count": 260}, {"open_bugs_count": 40}]},
        ]
    }


@pytest.fixture
def sample_security_data():
    """Sample security history JSON data"""
    return {"weeks": [{"metrics": {"current_total": 500}}, {"metrics": {"current_total": 475}}]}


@pytest.fixture
def sample_flow_data():
    """Sample flow history JSON data"""
    return {"weeks": [{"projects": [{"lead_time": {"p85": 45.5}}]}, {"projects": [{"lead_time": {"p85": 42.0}}]}]}


@pytest.fixture
def sample_deployment_data():
    """Sample deployment history JSON data"""
    return {
        "weeks": [
            {"projects": [{"build_success_rate": {"total_builds": 100, "succeeded": 90}}]},
            {"projects": [{"build_success_rate": {"total_builds": 50, "succeeded": 45}}]},
        ]
    }


@pytest.fixture
def sample_collaboration_data():
    """Sample collaboration history JSON data"""
    return {"weeks": [{"projects": [{"pr_merge_time": {"median_hours": 4.5}}]}]}


@pytest.fixture
def sample_ownership_data():
    """Sample ownership history JSON data"""
    return {"weeks": [{"projects": [{"unassigned": {"total_items": 100, "unassigned_count": 20}}]}]}


@pytest.fixture
def sample_risk_data():
    """Sample risk history JSON data"""
    return {"weeks": [{"projects": [{"code_churn": {"total_commits": 150}}]}]}


@pytest.fixture
def sample_baseline_security():
    """Sample ArmorCode baseline data"""
    return {"total_vulnerabilities": 500}


@pytest.fixture
def sample_baseline_bugs():
    """Sample ADO baseline data"""
    return {"open_count": 300}


@pytest.fixture
def temp_history_dir(tmp_path):
    """Create a temporary history directory"""
    history_dir = tmp_path / "observatory"
    history_dir.mkdir()
    return history_dir


# Test TrendsDataLoader Initialization


def test_data_loader_initialization():
    """Test TrendsDataLoader initialization with directory path"""
    loader = TrendsDataLoader(history_dir=".tmp/observatory")
    assert loader.history_dir == ".tmp/observatory"


def test_data_loader_initialization_with_path_object(tmp_path):
    """Test TrendsDataLoader accepts Path object"""
    loader = TrendsDataLoader(history_dir=tmp_path)
    assert loader.history_dir == tmp_path


# Test load_history_file() - Success Cases


def test_load_history_file_success(temp_history_dir, sample_quality_data, capsys):
    """Test successfully loading a valid history file"""
    # Create test file
    file_path = temp_history_dir / "quality_history.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sample_quality_data, f)

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("quality_history.json")

    assert result is not None
    assert result["weeks"] == sample_quality_data["weeks"]
    assert len(result["weeks"]) == 3

    # Check console output
    captured = capsys.readouterr()
    assert "quality_history.json: Loaded successfully" in captured.out
    assert "3 weeks" in captured.out


def test_load_history_file_with_many_weeks(temp_history_dir, capsys):
    """Test loading file with many weeks of data"""
    data: dict[str, list] = {"weeks": [{"projects": []} for _ in range(52)]}  # 52 weeks

    file_path = temp_history_dir / "long_history.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("long_history.json")

    assert result is not None
    assert len(result["weeks"]) == 52

    captured = capsys.readouterr()
    assert "52 weeks" in captured.out


# Test load_history_file() - Error Cases


def test_load_history_file_not_found(temp_history_dir, capsys):
    """Test loading non-existent file returns None"""
    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("nonexistent.json")

    assert result is None

    captured = capsys.readouterr()
    assert "File not found" in captured.out


def test_load_history_file_empty_file(temp_history_dir, capsys):
    """Test loading empty file returns None"""
    file_path = temp_history_dir / "empty.json"
    file_path.touch()  # Create empty file

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("empty.json")

    assert result is None

    captured = capsys.readouterr()
    assert "File is empty" in captured.out


def test_load_history_file_invalid_json(temp_history_dir, capsys):
    """Test loading file with invalid JSON returns None"""
    file_path = temp_history_dir / "invalid.json"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("{invalid json content")

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("invalid.json")

    assert result is None

    captured = capsys.readouterr()
    assert "JSON decode error" in captured.out


def test_load_history_file_not_dict(temp_history_dir, capsys):
    """Test loading file with non-dictionary data returns None"""
    file_path = temp_history_dir / "not_dict.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([1, 2, 3], f)  # Array instead of dict

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("not_dict.json")

    assert result is None

    captured = capsys.readouterr()
    assert "Invalid data structure" in captured.out


def test_load_history_file_missing_weeks_key(temp_history_dir, capsys):
    """Test loading file without 'weeks' key returns None"""
    file_path = temp_history_dir / "no_weeks.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"data": []}, f)

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("no_weeks.json")

    assert result is None

    captured = capsys.readouterr()
    assert "Missing 'weeks' key" in captured.out


def test_load_history_file_empty_weeks(temp_history_dir, capsys):
    """Test loading file with empty weeks array returns None"""
    file_path = temp_history_dir / "empty_weeks.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"weeks": []}, f)

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("empty_weeks.json")

    assert result is None

    captured = capsys.readouterr()
    assert "No weeks data found" in captured.out


def test_load_history_file_unicode_error(temp_history_dir, capsys):
    """Test handling of unicode decode errors"""
    file_path = temp_history_dir / "unicode_issue.json"
    with open(file_path, "wb") as f:
        f.write(b"\xff\xfe")  # Invalid UTF-8

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("unicode_issue.json")

    assert result is None

    captured = capsys.readouterr()
    # Will be either JSON decode error or Unicode decode error
    assert "error" in captured.out.lower()


# Test load_all_metrics()


def test_load_all_metrics_success(
    temp_history_dir,
    sample_quality_data,
    sample_security_data,
    sample_flow_data,
    sample_deployment_data,
    sample_collaboration_data,
    sample_ownership_data,
    sample_risk_data,
    capsys,
):
    """Test loading all 6 history files successfully"""
    # Create all history files
    files = {
        "quality_history.json": sample_quality_data,
        "security_history.json": sample_security_data,
        "flow_history.json": sample_flow_data,
        "deployment_history.json": sample_deployment_data,
        "collaboration_history.json": sample_collaboration_data,
        "ownership_history.json": sample_ownership_data,
        "risk_history.json": sample_risk_data,
    }

    for filename, data in files.items():
        file_path = temp_history_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_all_metrics()

    # Verify all metrics loaded
    assert "quality" in result
    assert "security" in result
    assert "flow" in result
    assert "deployment" in result
    assert "collaboration" in result
    assert "ownership" in result
    assert "risk" in result
    assert "baselines" in result

    # Verify data content
    assert result["quality"]["weeks"] == sample_quality_data["weeks"]
    assert result["security"]["weeks"] == sample_security_data["weeks"]

    # Check console output
    captured = capsys.readouterr()
    assert "Loading historical data..." in captured.out
    assert "quality_history.json: Loaded successfully" in captured.out


def test_load_all_metrics_partial_success(temp_history_dir, sample_quality_data, capsys):
    """Test load_all_metrics() when some files are missing"""
    # Only create quality file
    file_path = temp_history_dir / "quality_history.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(sample_quality_data, f)

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_all_metrics()

    # Quality should succeed, others should be None
    assert result["quality"] is not None
    assert result["security"] is None
    assert result["flow"] is None
    assert result["deployment"] is None
    assert result["collaboration"] is None
    assert result["ownership"] is None
    assert result["risk"] is None

    captured = capsys.readouterr()
    assert "File not found" in captured.out


def test_load_all_metrics_all_missing(temp_history_dir, capsys):
    """Test load_all_metrics() when all files are missing"""
    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_all_metrics()

    # All should be None
    assert all(v is None for k, v in result.items() if k != "baselines")

    captured = capsys.readouterr()
    assert captured.out.count("File not found") >= 6  # At least 6 missing files


# Test load_baseline_data()


def test_load_baseline_data_success(sample_baseline_security, sample_baseline_bugs, capsys):
    """Test loading baseline data successfully"""
    loader = TrendsDataLoader(history_dir=".tmp/observatory")

    # Mock the file system operations
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open()) as mock_file,
        patch("json.load") as mock_json_load,
    ):
        # Set up return values for json.load based on call order
        mock_json_load.side_effect = [sample_baseline_security, sample_baseline_bugs]

        result = loader.load_baseline_data()

        assert result["security"] == 500
        assert result["bugs"] == 300


def test_load_baseline_data_missing_files(capsys):
    """Test load_baseline_data() when files don't exist"""
    with patch("os.path.exists", return_value=False):
        loader = TrendsDataLoader(history_dir=Path(".tmp/observatory"))
        result = loader.load_baseline_data()

        assert result == {}


def test_load_baseline_data_invalid_json(tmp_path, capsys):
    """Test load_baseline_data() with invalid JSON"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create invalid JSON file
    with open(data_dir / "armorcode_baseline.json", "w", encoding="utf-8") as f:
        f.write("{invalid json")

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", return_value=open(data_dir / "armorcode_baseline.json", encoding="utf-8")),
    ):
        loader = TrendsDataLoader(history_dir=tmp_path)
        result = loader.load_baseline_data()

        # Should handle error gracefully
        assert "security" not in result or result.get("security") == 0

        captured = capsys.readouterr()
        assert "Failed to load" in captured.out or "error" in captured.out.lower()


def test_load_baseline_data_partial_success(sample_baseline_security, capsys):
    """Test load_baseline_data() when only one file exists"""
    loader = TrendsDataLoader(history_dir=".tmp/observatory")

    # Mock file system - only armorcode file exists
    def exists_side_effect(path):
        return "armorcode_baseline.json" in path

    with (
        patch("os.path.exists", side_effect=exists_side_effect),
        patch("builtins.open", mock_open()) as mock_file,
        patch("json.load", return_value=sample_baseline_security),
    ):
        result = loader.load_baseline_data()

        # Security should succeed, bugs should be missing
        assert result.get("security") == 500
        assert "bugs" not in result


# Test Edge Cases


def test_load_history_file_with_nested_data(temp_history_dir, capsys):
    """Test loading file with deeply nested data structures"""
    complex_data = {
        "weeks": [
            {
                "projects": [
                    {
                        "name": "Project A",
                        "metrics": {"nested": {"deeply": {"value": 123}}},
                        "work_type_metrics": {"Feature": {"lead_time": {"p85": 45.5}}},
                    }
                ]
            }
        ]
    }

    file_path = temp_history_dir / "complex.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(complex_data, f)

    loader = TrendsDataLoader(history_dir=temp_history_dir)
    result = loader.load_history_file("complex.json")

    assert result is not None
    assert result["weeks"][0]["projects"][0]["name"] == "Project A"


def test_data_loader_with_absolute_path():
    """Test TrendsDataLoader works with absolute paths"""
    loader = TrendsDataLoader(history_dir=Path("C:/DEV/Agentic-Test/.tmp/observatory"))
    assert loader.history_dir == Path("C:/DEV/Agentic-Test/.tmp/observatory")


def test_data_loader_with_relative_path():
    """Test TrendsDataLoader works with relative paths"""
    loader = TrendsDataLoader(history_dir=".tmp/observatory")
    assert loader.history_dir == ".tmp/observatory"
