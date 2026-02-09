"""
Test Suite for HTML Sanitizer

Tests XSS prevention with legitimate inputs, edge cases, and
malicious attack vectors to ensure robust security.

Run with:
    pytest tests/security/test_html_sanitizer.py -v
"""

import os
import sys

import pytest

from execution.security import HTMLSanitizer, safe_html


class TestHTMLSanitizer:
    """Tests for XSS prevention"""

    def test_escape_script_tags(self):
        """Test that <script> tags are escaped"""
        xss = "<script>alert('XSS')</script>"
        result = HTMLSanitizer.escape_html(xss)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_escape_img_onerror(self):
        """Test that img onerror XSS is escaped"""
        xss = '<img src=x onerror=alert("XSS")>'
        result = HTMLSanitizer.escape_html(xss)
        assert "<img" not in result
        assert "&lt;img" in result

    def test_escape_event_handlers(self):
        """Test that event handlers are escaped"""
        xss = "<div onclick=\"alert('XSS')\">Click</div>"
        result = HTMLSanitizer.escape_html(xss)
        # Tags should be escaped (< and > converted to entities)
        assert "<div" not in result
        assert "&lt;div" in result
        # The escaped version is safe even if "onclick=" string remains

    def test_escape_javascript_protocol(self):
        """Test that javascript: protocol is escaped"""
        xss = "<a href=\"javascript:alert('XSS')\">Click</a>"
        result = HTMLSanitizer.escape_html(xss)
        # Tags should be escaped (< and > converted to entities)
        assert "<a" not in result
        assert "&lt;a" in result
        # The escaped version is safe even if "javascript:" string remains

    def test_escape_svg_onload(self):
        """Test that SVG onload XSS is escaped"""
        xss = '<svg/onload=alert("XSS")>'
        result = HTMLSanitizer.escape_html(xss)
        assert "<svg" not in result
        assert "&lt;svg" in result

    def test_escape_iframe(self):
        """Test that iframe injection is escaped"""
        xss = "<iframe src=\"javascript:alert('XSS')\"></iframe>"
        result = HTMLSanitizer.escape_html(xss)
        assert "<iframe" not in result
        assert "&lt;iframe" in result

    def test_escape_normal_text(self):
        """Test that normal text is preserved"""
        text = "Hello, World!"
        result = HTMLSanitizer.escape_html(text)
        assert result == text

    def test_escape_text_with_ampersand(self):
        """Test that ampersands are escaped"""
        text = "Tom & Jerry"
        result = HTMLSanitizer.escape_html(text)
        assert result == "Tom &amp; Jerry"

    def test_escape_none(self):
        """Test that None values are handled"""
        result = HTMLSanitizer.escape_html(None)
        assert result == ""

    def test_escape_html_attribute(self):
        """Test attribute-specific escaping"""
        text = '<script>alert("XSS")</script>'
        result = HTMLSanitizer.escape_html_attribute(text)
        assert "<script>" not in result

    def test_escape_javascript_string(self):
        """Test JavaScript string escaping"""
        text = "'; alert('XSS'); var x='"
        result = HTMLSanitizer.escape_javascript_string(text)
        assert "\\'" in result
        assert "alert" in result  # Content preserved but escaped

    def test_safe_html_convenience_function(self):
        """Test convenience wrapper function"""
        xss = "<script>alert('XSS')</script>"
        result = safe_html(xss)
        assert "<script>" not in result
