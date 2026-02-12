# Push Workflow

Execute a complete test-commit-push cycle with verification.

## Steps

1. Run `pytest tests/ -v` and confirm all tests pass
2. Run `git status` to check for uncommitted changes
3. If uncommitted changes exist:
   - Stage relevant files with `git add`
   - Create a commit with a descriptive conventional commit message
   - Include Co-Authored-By line: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`
4. Run `git push origin main`
5. Verify push succeeded with final `git status` and `git log -1`
6. Report final summary of what was committed and pushed

## Important Notes

- Do NOT commit if tests fail - fix issues first
- Use conventional commit format: `feat:`, `fix:`, `chore:`, `refactor:`
- Ensure all quality gates passed before committing
- Report clear success/failure status to user
