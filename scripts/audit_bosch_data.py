"""Run the ETCH-GATE Milestone 1 BOSCH data audit."""

import argparse
import json
from pathlib import Path

from etch_gate.data import audit_bosch_data


def parse_args() -> argparse.Namespace:
    """Parse raw-data and output paths."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    """Audit the immutable source files and persist machine-readable results."""

    args = parse_args()
    result = audit_bosch_data(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
