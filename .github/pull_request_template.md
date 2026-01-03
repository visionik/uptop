## Description

<!-- Provide a clear and concise description of your changes -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test coverage improvement
- [ ] Build/CI configuration change

## Related Issues

<!-- Link related issues using keywords like "Closes #123" or "Fixes #456" -->

Closes #
Related to #

## Changes Made

<!-- Provide a detailed list of changes -->

- Change 1
- Change 2
- Change 3

## Testing

### Test Coverage

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally (`task test`)
- [ ] Code coverage maintained or improved (≥75%)

### Manual Testing

<!-- Describe how you tested your changes -->

**Test Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python Version: [e.g., 3.11.5]

**Test Steps:**
1. Step 1
2. Step 2
3. Step 3

**Test Results:**
- [ ] TUI mode tested and working
- [ ] CLI mode tested and working
- [ ] Feature works as expected
- [ ] No regressions observed

## Code Quality Checklist

- [ ] Code follows project style guidelines (black, isort, ruff)
- [ ] Code passes type checking (`task type`)
- [ ] All linting checks pass (`task lint`)
- [ ] Pre-commit checks pass (`task check`)
- [ ] Code is well-documented (docstrings for public APIs)
- [ ] No files exceed 1000 lines (preferably < 500 lines)
- [ ] Type hints added for all functions/methods

## Documentation

- [ ] Documentation updated (if user-facing changes)
- [ ] README.md updated (if needed)
- [ ] CHANGELOG.md updated (will be auto-generated from commits)
- [ ] Configuration examples updated (if config changes)
- [ ] Plugin development guide updated (if plugin API changes)

## Commit Messages

- [ ] All commits follow [Conventional Commits](https://www.conventionalcommits.org/) format
- [ ] Commit messages are clear and descriptive
- [ ] Breaking changes are clearly marked in commit messages

## Breaking Changes

<!-- If this PR includes breaking changes, describe them here -->

**Breaking Changes:**
- [ ] No breaking changes
- [ ] Breaking changes included (describe below)

**Description of Breaking Changes:**

<!-- Explain what breaks and how users should migrate -->

## Screenshots/Output

<!-- If applicable, add screenshots or terminal output showing your changes -->

### Before
```
<!-- Paste before output here -->
```

### After
```
<!-- Paste after output here -->
```

## Performance Impact

<!-- Describe any performance implications of your changes -->

- [ ] No performance impact
- [ ] Performance improvement (describe below)
- [ ] Potential performance degradation (describe below and justify)

**Performance Notes:**

## Dependencies

<!-- List any new dependencies added -->

- [ ] No new dependencies
- [ ] New dependencies added (list below)

**New Dependencies:**
- Dependency name and version
- Reason for adding

## Deployment Notes

<!-- Any special considerations for deployment? -->

- [ ] No special deployment considerations
- [ ] Requires configuration migration
- [ ] Requires database migration
- [ ] Requires environment variable changes

**Deployment Instructions:**

## Reviewer Notes

<!-- Any specific areas you'd like reviewers to focus on? -->

**Focus Areas:**
- Area to review carefully
- Specific concerns or questions

## Post-Merge Tasks

<!-- Tasks to complete after this PR is merged -->

- [ ] Update documentation website
- [ ] Announce breaking changes (if any)
- [ ] Create follow-up issues
- [ ] Update plugin examples

## Checklist

<!-- Final checklist before requesting review -->

- [ ] I have read the [CONTRIBUTING.md](../CONTRIBUTING.md) guide
- [ ] My code follows the project's code style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published
- [ ] I have run `task check` and all checks pass
- [ ] I have updated the CONTRIBUTING.md if I added new processes or requirements

## Additional Notes

<!-- Any additional information for reviewers -->
