"""
Tests for execution.framework.theme module
"""

import pytest

from execution.framework.theme import get_color_palette_docs, get_theme_variables


class TestThemeVariables:
    """Test theme variable generation"""

    def test_get_theme_variables_default_colors(self):
        """Test theme variables with default colors"""
        css = get_theme_variables()
        assert ":root {" in css
        assert '[data-theme="dark"]' in css
        assert "--bg-primary" in css
        assert "--text-primary" in css
        assert "--color-rag-green: #10b981" in css
        assert "--spacing-md: 16px" in css

    def test_get_theme_variables_custom_colors(self):
        """Test theme variables with custom brand colors"""
        css = get_theme_variables(primary_color="#8b5cf6", secondary_color="#7c3aed")
        assert "--header-gradient-start: #8b5cf6" in css
        assert "--header-gradient-end: #7c3aed" in css

    def test_theme_variables_contains_all_sections(self):
        """Test that all required sections are present"""
        css = get_theme_variables()
        assert "/* Background Colors */" in css
        assert "/* Text Colors */" in css
        assert "/* RAG Status Colors */" in css
        assert "/* Spacing Scale */" in css

    def test_color_palette_docs_structure(self):
        """Test color palette documentation structure"""
        docs = get_color_palette_docs()
        assert "backgrounds" in docs
        assert "text" in docs
        assert "rag_colors" in docs
        assert "spacing_scale" in docs
        assert docs["spacing_scale"]["md"] == "16px - Medium spacing (card padding, section gaps)"
