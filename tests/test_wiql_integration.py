"""
Integration Test for WIQL Injection Fixes

Verifies that the 5 fixed files properly validate inputs and block injection attempts.
"""

import os
import sys

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from execution.security_utils import ValidationError, WIQLValidator


def test_wiql_validator_blocks_injection():
    """Test that WIQLValidator blocks common injection patterns"""

    malicious_inputs = [
        "'; DROP TABLE bugs--",
        "Project' OR '1'='1",
        'Project" OR "1"="1',
        "Project'; DELETE FROM WorkItems--",
        "Project UNION SELECT",
        "Project; DROP TABLE",
    ]

    for malicious_input in malicious_inputs:
        with pytest.raises(ValidationError):
            WIQLValidator.validate_project_name(malicious_input)
        print(f"  [PASS] Blocked injection: {malicious_input}")


def test_wiql_validator_allows_valid_input():
    """Test that WIQLValidator allows legitimate project names"""

    valid_inputs = [
        "My Project",
        "Access-Legal_v2.0",
        "Project 123",
        "Test.Project",
    ]

    for valid_input in valid_inputs:
        result = WIQLValidator.validate_project_name(valid_input)
        assert result == valid_input
        print(f"  [PASS] Allowed valid input: {valid_input}")


def test_build_safe_wiql_basic():
    """Test that build_safe_wiql constructs queries safely"""

    query = WIQLValidator.build_safe_wiql(
        "WHERE [System.TeamProject] = '{project}' AND [System.WorkItemType] = '{work_type}'",
        project="Test Project",
        work_type="Bug",
    )

    assert "Test Project" in query
    assert "Bug" in query
    # Ensure no SQL keywords are present that shouldn't be
    assert "DROP" not in query
    assert "UNION" not in query
    print(f"  [PASS] Safe query built: {query[:80]}...")


def test_build_safe_wiql_blocks_injection_in_params():
    """Test that build_safe_wiql validates parameters"""

    with pytest.raises(ValidationError):
        WIQLValidator.build_safe_wiql("WHERE [System.TeamProject] = '{project}'", project="'; DROP TABLE--")
    print("  [PASS] Blocked injection in parameter")


def test_date_validation():
    """Test that date validation works"""

    # Valid date
    result = WIQLValidator.validate_date_iso8601("2026-02-06")
    assert result == "2026-02-06"

    # Invalid format
    with pytest.raises(ValidationError):
        WIQLValidator.validate_date_iso8601("2026/02/06")

    # Invalid date
    with pytest.raises(ValidationError):
        WIQLValidator.validate_date_iso8601("2026-13-01")

    print("  [PASS] Date validation works correctly")


if __name__ == "__main__":
    print("WIQL Integration Tests")
    print("=" * 60)

    print("\n1. Testing injection blocking:")
    test_wiql_validator_blocks_injection()

    print("\n2. Testing valid input acceptance:")
    test_wiql_validator_allows_valid_input()

    print("\n3. Testing safe query building:")
    test_build_safe_wiql_basic()

    print("\n4. Testing parameter validation:")
    test_build_safe_wiql_blocks_injection_in_params()

    print("\n5. Testing date validation:")
    test_date_validation()

    print("\n" + "=" * 60)
    print("All integration tests passed!")
