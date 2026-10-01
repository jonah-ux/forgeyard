# Architecture

The first slice has two layers:

```text
CLI → TaskRecord → Evidence → JSON receipt
```

The core is deliberately independent of model providers, shell execution, Git, and network
services. Future adapters will sit outside `core.py` and must return explicit evidence rather than
changing task status directly. The task record is the integration seam for worktree execution,
verification, review packets, and resume support.
