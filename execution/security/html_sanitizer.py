"""
HTML Sanitizer for XSS Prevention

Sanitizes HTML output to prevent Cross-Site Scripting (XSS) attacks.
Use this when generating HTML from user-supplied or external data.

For production use, consider migrating to Jinja2 with auto-escaping.

Author: Security Audit Implementation
Date: 2026-02-06
Refactored: 2026-02-08
"""


class HTMLSanitizer:
    """
    Sanitizes HTML output to prevent Cross-Site Scripting (XSS) attacks.

    Use this when generating HTML from user-supplied or external data.
    For production use, consider migrating to Jinja2 with auto-escaping.
    """

    # HTML entities that must be escaped
    HTML_ESCAPES = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
        "/": "&#x2F;",
    }

    @staticmethod
    def escape_html(text: str | None) -> str:
        """
        Escape HTML special characters to prevent XSS.

        This provides defense-in-depth against XSS attacks. Ideally, use
        a templating engine with auto-escaping (like Jinja2).

        Args:
            text: Text to escape (may be None)

        Returns:
            Escaped text safe for HTML context

        Example:
            >>> HTMLSanitizer.escape_html("<script>alert('XSS')</script>")
            '&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;'
        """
        if text is None:
            return ""

        text = str(text)

        # Escape each special character
        for char, escape in HTMLSanitizer.HTML_ESCAPES.items():
            text = text.replace(char, escape)

        return text

    @staticmethod
    def escape_html_attribute(text: str | None) -> str:
        """
        Escape text for use in HTML attributes.

        More strict than regular escaping - removes control characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for HTML attribute context
        """
        if text is None:
            return ""

        text = str(text)

        # Remove control characters (ASCII < 32, except space)
        text = "".join(char for char in text if ord(char) >= 32 or char == " ")

        # Escape HTML entities
        return HTMLSanitizer.escape_html(text)

    @staticmethod
    def escape_javascript_string(text: str | None) -> str:
        """
        Escape text for use in JavaScript string context.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for JavaScript string context
        """
        if text is None:
            return ""

        text = str(text)

        # Escape JavaScript special characters
        js_escapes = {
            "\\": "\\\\",
            "'": "\\'",
            '"': '\\"',
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
            "<": "\\x3C",  # Prevent </script> injection
            ">": "\\x3E",
        }

        for char, escape in js_escapes.items():
            text = text.replace(char, escape)

        return text
