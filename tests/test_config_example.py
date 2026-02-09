"""
Test Configuration - Example Template

This file contains test data/fixtures. Copy to test_config.py and customize
for your environment.

Usage:
    cp tests/test_config.example.py tests/test_config.py
    # Edit test_config.py with your project names

Note: test_config.py is gitignored - it won't be committed to the repository.
"""

# Product/Project Names for Tests
# These are used as test fixtures in dashboard and integration tests
TEST_PRODUCTS = {
    "product1": "Product One",
    "product2": "Product Two",
    "product3": "Product Three",
}

# Project Names for Integration Tests
TEST_PROJECTS = {
    "legal": "Legal Project",
    "finance": "Finance Project",
}

# Area Paths for Testing
TEST_AREA_PATHS = {
    "main": "Main Project\\Main Area",
    "sub": "Main Project\\Sub Area",
}
