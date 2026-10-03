# Contributing

Small, reviewable changes are preferred. Start with a failing or missing contract, add the smallest
implementation, then add boundary tests and documentation. Do not add provider credentials or
real repository data to fixtures.

Before opening a pull request, run:

```bash
python3 -m pytest -q
python3 -m compileall -q src tests
git diff --check
```

Explain the behavior change, the evidence that proves it, and any limitation that remains.
