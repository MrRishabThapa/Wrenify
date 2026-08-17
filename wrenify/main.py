"""
Wrenify — Main Entry Point

Run with:
    poetry run wrenify
    python -m wrenify
"""

import sys


def main() -> None:
    from wrenify.ui.app import run

    try:
        sys.exit(run())
    except Exception as exc:
        print(f"Failed to launch the Wrenify UI: {exc}", file=sys.stderr)
        print(
            "Tip: on Wayland, try 'export QT_QPA_PLATFORM=xcb' "
            "and run again.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
