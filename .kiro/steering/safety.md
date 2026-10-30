# Safety and Cost Constraints

- Heuristics are data (structured rules interpreted by our code), not executable code. If a later spec allows generated code, it must run in a sandbox with no filesystem or network access and a CPU/time limit.
- Enforce budgets: `MAX_LLM_CALLS_PER_GENERATION` and `MAX_GENERATIONS` from `.env`. Stop the run cleanly when a budget is hit.
- Credit assignment must be based on measured score changes in the simulator, never on a heuristic's self-report.
- The auditor flags heuristics whose worth rises without a matching score contribution (the Eurisko parasite pattern) and demotes them. Log every audit decision.
- Never commit `.env`, API keys or large raw run logs. Only curated demo runs go in `runs/demo/`.
