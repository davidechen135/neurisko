"""Record the two H59 demo runs: same seed and config, auditor off and on, no LLM.

Uses the configuration of tests/engine/test_auditor.py::test_h59_demo, where M5 Clone tops the
meta table without the auditor on 8 of 8 seeds. Anyone can reproduce these runs.

Run: uv run python scripts/record_h59_demo.py [--seed 0] [--generations 9]
"""

import argparse
import shutil
from pathlib import Path

from neurisko.engine.evolve import EvolveConfig
from neurisko.runs.session import start_run

OUT = Path("runs/demo")
GAME = dict(n_random=6, n_seeds=2)
ENGINE = dict(population=12, design_apps=24, immigrants=2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--generations", type=int, default=9)
    args = ap.parse_args()
    for name, auditor in (("h59-off", False), ("h59-on", True)):
        run_dir = OUT / name
        if run_dir.exists():
            shutil.rmtree(run_dir)
        cfg = EvolveConfig(generations=args.generations, seed=args.seed, auditor=auditor, **ENGINE)
        ev, res = start_run(cfg, None, run_dir, game_settings=GAME)
        ranked = sorted(ev.metas.values(), key=lambda m: -m.worth)
        print(
            f"{name}: " + "  ".join(f"{m.id} {m.worth:.0f}{'!' if m.flags else ''}" for m in ranked)
        )


if __name__ == "__main__":
    main()
