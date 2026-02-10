"""
Usage Tables Report - Submodules

This package contains modular components for generating AI usage tables reports.
"""

from execution.reports.usage_tables.data_loader import read_excel_usage_data
from execution.reports.usage_tables.data_processor import (
    calculate_summary_stats,
    filter_by_access_status,
    filter_by_usage_threshold,
    filter_team_users,
    get_usage_intensity_distribution,
    normalize_access_column_value,
    prepare_claude_data,
    prepare_devin_data,
)
from execution.reports.usage_tables.interactive_uploader import (
    generate_data_processing_js,
    generate_file_upload_handler_js,
    generate_import_button_html,
    generate_import_button_styles,
    generate_papaparse_script_tag,
    generate_placeholder_html,
    generate_utility_functions_js,
)
from execution.reports.usage_tables.table_generator import (
    AccessBadgeType,
    HeatmapColor,
    TableRow,
    generate_access_badge_html,
    generate_heatmap_cell_html,
    generate_table_html,
    generate_table_row_html,
    get_usage_heatmap_color,
)

__all__ = [
    # Data loader
    "read_excel_usage_data",
    # Data processor functions
    "filter_team_users",
    "prepare_claude_data",
    "prepare_devin_data",
    "calculate_summary_stats",
    "normalize_access_column_value",
    "filter_by_access_status",
    "filter_by_usage_threshold",
    "get_usage_intensity_distribution",
    # Interactive uploader functions
    "generate_import_button_html",
    "generate_placeholder_html",
    "generate_file_upload_handler_js",
    "generate_data_processing_js",
    "generate_utility_functions_js",
    "generate_import_button_styles",
    "generate_papaparse_script_tag",
    # Table generator functions
    "AccessBadgeType",
    "HeatmapColor",
    "TableRow",
    "generate_access_badge_html",
    "generate_heatmap_cell_html",
    "generate_table_html",
    "generate_table_row_html",
    "get_usage_heatmap_color",
]
