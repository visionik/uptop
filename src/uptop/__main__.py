"""Main entry point for uptop CLI."""

import sys

from uptop.cli import cli_main


def main() -> int:
    """Main entry point for uptop.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        cli_main()
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
    except KeyboardInterrupt:
        return 130  # Standard exit code for SIGINT


if __name__ == "__main__":
    sys.exit(main())
