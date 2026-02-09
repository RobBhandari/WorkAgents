# AI Contributions Dashboard - REMOVED

## Status
**REMOVED** as of 2026-02-03

## Reason
The AI contributions detection method was not reliable enough for production use. It relied on keyword-based heuristics (searching for "devin" in PR metadata) which had:

- **False positives**: Human developers named "Devin", PRs mentioning Devin
- **False negatives**: Devin PRs without standard naming, human-submitted Devin code
- **Estimated confidence**: ~70% at best

## Recommendation for Future
To reintroduce this dashboard with reliable data:

1. **Query Devin directly** via API for ground truth
2. Alternatively, establish proper tagging conventions in ADO (e.g., "AI-Generated" tags)
3. Get Devin API credentials to retrieve definitive PR lists
4. Cross-reference Devin's PR list with ADO data

## Files (Preserved for Future Use)
- `execution/analyze_devin_prs.py` - Detection logic
- `execution/generate_ai_dashboard.py` - Dashboard generator
- `.tmp/observatory/dashboards/ai_contributions.html` - Dashboard HTML (if exists)

## Decision Made By
User decision - removed due to insufficient data reliability

## Notes
Link removed from main index.html (2026-02-03)
Files kept in repository for future implementation with better data sources
