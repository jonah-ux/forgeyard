# Limitations

The 0.1.0 foundation does not execute agent commands, invoke model providers, resume interrupted
processes, or merge code. It can validate a worktree request and create a detached checkout with a
bounded Git invocation, but it does not yet capture commands, preserve dirty source state, or
produce a review packet. It defines and verifies the evidence contract those later slices will use.
Treat the JSON record as a review input, not proof of deployment or runtime behavior.
