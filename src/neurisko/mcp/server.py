"""`neurisko-mcp`: stdio MCP server exposing Neurisko's balance tools.

Tools run as sync handlers; the MCP SDK runs those on worker threads, so long measurements do
not block the protocol. Nothing here calls an LLM: Kiro's own model explains the numbers.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from neurisko.mcp import tools as T
from neurisko.mcp.paths import workspace_root

INSTRUCTIONS = """\
Neurisko measures game balance for Monster Mash ruleset files (TOML) by simulation and by
evolving teams with a Eurisko-style heuristic engine. All tools take a workspace-relative path
to a ruleset file, e.g. rulesets/monster-mash.toml, and never modify it.
- check_ruleset: validate and summarise a file (fast).
- simulate_battle / score_team: one battle, or a team's win rate against fixed opponents (fast).
- quick_balance: dominant and underused units over 4 seeds (about 20-40 s).
- verify_patch: test one stat change on the same seeds (about 20-40 s).
- start_report + report_status: full 8-seed report with verified fixes (about 2 min, as a job).
Quote numbers with their baseline and seed count. Recommend a change only after verify_patch or
a report marks it effective."""


def build_server(jobs: T.ReportJobs | None = None) -> MCPServer:
    jobs = jobs or T.ReportJobs(reports_dir=workspace_root() / "reports")
    s = MCPServer("neurisko", title="Neurisko balance lab", instructions=INSTRUCTIONS)

    @s.tool()
    def check_ruleset(path: str) -> T.RulesetSummary:
        """Validate a ruleset TOML file and summarise units, synergies and limits.

        Returns valid=false with field-level errors if the file does not load."""
        return T.check_ruleset(path)

    @s.tool()
    def simulate_battle(
        path: str, team_a: list[str], team_b: list[str], seed: int = 0
    ) -> T.BattleSummary:
        """Simulate one deterministic battle. Teams are unit ids, front first."""
        return T.simulate_battle(path, team_a, team_b, seed)

    @s.tool()
    def score_team(path: str, team: list[str]) -> T.TeamScore:
        """Win rate of a team (unit ids, front first) against the fixed opponent pool."""
        return T.score_team(path, team)

    @s.tool()
    def quick_balance(path: str) -> T.QuickBalance:
        """Quick balance check (4 engine runs): unit shares in strong vs random teams, with
        dominant and underused units. Takes about 20-40 seconds."""
        return T.quick_balance(path)

    @s.tool()
    def verify_patch(path: str, unit: str, field: T.Field, new_value: float) -> T.PatchCheck:
        """Test one stat change (e.g. unit=witch, field=cost, new_value=3) by re-running the
        quick check on the patched rules with the same seeds. Does not edit the file.
        Takes about 20-40 seconds."""
        return T.verify_patch(path, unit, field, new_value)

    @s.tool()
    def start_report(path: str) -> T.JobStatus:
        """Start a full balance report (8 seeds, verified fixes, about 2 minutes) in the
        background. Returns a job_id for report_status."""
        return jobs.start(path)

    @s.tool()
    def report_status(job_id: str) -> T.JobStatus:
        """State of a report job; when done, the summary and the path of report.md."""
        return jobs.status(job_id)

    @s.prompt()
    def balance_review(path: str = "rulesets/monster-mash.toml") -> str:
        """Measure a ruleset's balance and propose verified fixes."""
        return (
            f"Review the balance of {path} with the neurisko tools:\n"
            f"1. check_ruleset on {path}; stop and list the errors if it is invalid.\n"
            "2. quick_balance. List dominant and underused units with their share in strong "
            "teams, the random baseline, the range and the seed count.\n"
            "3. For each dominant unit, propose at most 2 single-stat changes and run "
            "verify_patch on each.\n"
            "4. Summarise in at most 10 lines: what dominates and by how much, which changes "
            "were effective (with before/after numbers), and which failed and why. Recommend "
            "only changes verify_patch marked effective. Do not edit the file."
        )

    return s


def main() -> None:
    # stdout carries the MCP protocol: nothing else may print to it.
    build_server().run("stdio")


if __name__ == "__main__":
    main()
