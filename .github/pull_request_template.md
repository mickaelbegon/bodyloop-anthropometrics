## Summary

<!-- 1-3 bullet points describing what this PR changes. -->

-
-

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature / implementation
- [ ] Refactor / cleanup
- [ ] Scientific decision (requires validation)
- [ ] Documentation
- [ ] CI / configuration

## Scientific impact

<!-- Does this PR change any computation that affects BSP outputs?
     If yes, describe the expected impact and provide validation evidence. -->

- [ ] No scientific impact
- [ ] Changes computation — validation evidence provided below

**Validation evidence:**

## Checklist

- [ ] All new functions have NumPy-style docstrings with `Parameters`, `Returns`, `Raises`, `Notes`, `References`
- [ ] `TODO_SCIENTIFIC` markers added where scientific decisions are deferred
- [ ] `SCIENCE_DECISIONS.md` updated if a previously open decision is resolved
- [ ] Unit tests added in `tests/unit/`
- [ ] `ruff check .` and `ruff format .` pass locally
- [ ] `mypy bodyloop_anthropometrics` passes locally
- [ ] No real patient data committed

## Related issues

Closes #<!-- issue number -->
