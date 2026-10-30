"""Command-line interface: `neurisko battle` and `neurisko score`."""

from __future__ import annotations

import argparse
import sys

from neurisko.engine.game import BattleResult, Event
from neurisko.games.autobattler import MonsterMash, RulesetError

EXIT_USAGE = 2


def _parse_design(text: str) -> tuple[str, ...]:
    return tuple(p.strip() for p in text.split(",") if p.strip())


def _load_game(args: argparse.Namespace) -> MonsterMash:
    try:
        return MonsterMash.from_file(args.ruleset)
    except RulesetError as err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(EXIT_USAGE)


def _check(game: MonsterMash, label: str, design: tuple[str, ...]) -> None:
    errors = game.validate(design)
    if errors:
        print(f"error: {label} is invalid:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(EXIT_USAGE)


def _format_event(e: Event) -> str:
    t = f"t{e.tick:>4}"
    match e.kind:
        case "attack":
            return f"{t}  {e.actor:<18} hits   {e.target:<18} {e.amount:>4}"
        case "dodge":
            return f"{t}  {e.actor:<18} dodges {e.target}"
        case "heal":
            return f"{t}  {e.actor:<18} heals  {e.target:<18} {e.amount:>4}"
        case "summon":
            return f"{t}  {e.actor:<18} raises {e.target}"
        case "death":
            return f"{t}  {e.actor:<18} DIES"
        case _:
            state = "ON " if e.kind == "synergy_on" else "OFF"
            return f"{t}  synergy {state} {e.actor}"


def _print_result(r: BattleResult) -> None:
    print()
    banner = "DRAW" if r.winner == "draw" else f"TEAM {r.winner} WINS"
    print(f"== {banner} after {r.ticks} ticks ==")
    print(f"{'unit':<18} {'dealt':>6} {'taken':>6} {'kills':>5} {'heal':>5} {'raise':>5}  alive")
    for s in r.stats:
        alive = "yes" if s.survived else "-"
        print(
            f"{s.label:<18} {s.damage_dealt:>6} {s.damage_taken:>6} {s.kills:>5} "
            f"{s.healing:>5} {s.summons:>5}  {alive}"
        )


def cmd_battle(args: argparse.Namespace) -> int:
    game = _load_game(args)
    a, b = _parse_design(args.a), _parse_design(args.b)
    _check(game, "team A", a)
    _check(game, "team B", b)
    print(f"ruleset {game.ruleset_hash}  seed {args.seed}")
    print(f"A {game.describe(a)}")
    print(f"B {game.describe(b)}")
    result = game.simulate(a, b, args.seed, log=not args.quiet)
    if result.events:
        print()
        for e in result.events:
            print(_format_event(e))
    _print_result(result)
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    game = _load_game(args)
    d = _parse_design(args.design)
    _check(game, "design", d)
    report = game.score(d)
    print(f"ruleset {game.ruleset_hash}  {game.describe(d)}")
    print()
    print(f"{'opponent':<18} {'W':>3} {'D':>3} {'L':>3}  score  design")
    by_name = {o.name: o.design for o in game.gauntlet}
    for m in report.matchups:
        bar = "#" * round(m.score * 10)
        print(
            f"{m.opponent:<18} {m.wins:>3} {m.draws:>3} {m.losses:>3}  {m.score:.2f}  "
            f"{bar:<10} {', '.join(by_name[m.opponent])}"
        )
    print()
    print(f"== SCORE {report.score:.3f} over {report.battles} battles ==")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neurisko", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ruleset", default=None, help="ruleset TOML (default: packaged v0)")

    p = sub.add_parser("battle", parents=[common], help="simulate one battle")
    p.add_argument("a", help="team A, comma-separated unit ids, front first")
    p.add_argument("b", help="team B, comma-separated unit ids, front first")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--quiet", action="store_true", help="hide the event log")
    p.set_defaults(func=cmd_battle)

    p = sub.add_parser("score", parents=[common], help="score a team against the gauntlet")
    p.add_argument("design", help="comma-separated unit ids, front first")
    p.set_defaults(func=cmd_score)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
