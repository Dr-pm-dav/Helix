"""
Compare a deliberately small QAOA dispatch experiment with the classical optimum.

Builds a unit-commitment QUBO (cover a target load at minimum cost), solves it
exactly by enumeration, and solves it again with a compact statevector QAOA,
then reports whether QAOA recovered the optimum. This makes no
quantum-advantage claim; it is a workflow demonstration on a small instance.

    python scripts/run_dispatch.py
    python scripts/run_dispatch.py --target 16 --layers 4
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from helix.dispatch import DEFAULT_UNITS, dispatch_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description="QAOA vs classical economic dispatch")
    parser.add_argument("--target", type=float, default=None,
                        help="target load to cover (100-MW blocks); default ~55%% of fleet")
    parser.add_argument("--penalty", type=float, default=10.0)
    parser.add_argument("--layers", type=int, default=4, help="QAOA depth p")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()

    print(f"Dispatch fleet ({len(DEFAULT_UNITS)} units, {len(DEFAULT_UNITS)}-qubit QUBO):")
    for u in DEFAULT_UNITS:
        print(f"  {u['name']:8s} capacity {u['capacity']:>4} (x100 MW)   cost ${u['cost']:.0f}/MWh")

    result = dispatch_experiment(target_load=args.target, penalty=args.penalty,
                                 p=args.layers, seed=args.seed)
    ex, qa = result["exact"], result["qaoa"]
    print(f"\nTarget load to cover: {result['target_load']} (x100 MW)")
    print(f"  classical optimum : ${ex['cost']:.2f}  commit {ex['committed']}  "
          f"served {ex['served_capacity']}")
    print(f"  QAOA (p={qa['p']})        : ${qa['cost']:.2f}  commit {qa['committed']}  "
          f"served {qa['served_capacity']}")
    print(f"  optimum recovered : {result['optimum_recovered']}  "
          f"(QAOA probability on this solution {qa['prob_of_solution']:.3f})")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    json.dump(result, open(out / "dispatch_result.json", "w"), indent=2)
    print(f"\n  wrote {out / 'dispatch_result.json'}")
    print("  NOTE: statevector QAOA on a small instance; no quantum-advantage claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
