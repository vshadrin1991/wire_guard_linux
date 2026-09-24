"""Entry point: python3 -m wg_indicator [--interface wg0]"""
from __future__ import annotations

import argparse
import sys

from .instance import acquire_lock, lock_path
from .tunnel import validate_interface


def _interface(value: str) -> str:
    try:
        return validate_interface(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wireguard-indicator",
        description="Top-bar on/off switch for a wg-quick WireGuard interface.",
    )
    parser.add_argument(
        "-i",
        "--interface",
        type=_interface,
        default="wg0",
        help="WireGuard interface to control (default: wg0)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    lock = acquire_lock(lock_path(args.interface))  # held until main() returns
    if lock is None:
        print(f"wireguard-indicator for {args.interface} is already running", file=sys.stderr)
        return 1
    from .app import run  # GTK is imported only here, so everything above is testable on macOS

    run(args.interface)
    return 0


if __name__ == "__main__":
    sys.exit(main())
