# Parallel documentation handoffs

Workers create `RM-<real-issue-number>.md` from [TEMPLATE.md](TEMPLATE.md). One issue owns one file;
do not append to a shared log. The [parallel-work rule](../../.agent/rules/parallel-work.md) defines timing
and ownership; the [delivery guide](../PARALLEL-FEATURE-DELIVERY.md) maps feature dependencies/conflicts.

These notes let workers keep implementing while the integrator reconciles canonical shared documents.
They are not delivery state, approved policy or an exemption from same-PR documentation. Ready PRs must
have a reconciled handoff and actual canonical edits in their own diff. Include no secrets or real PII.
