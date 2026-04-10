"""OPENCLI entry point."""

import sys
from opencli.tui.app import OrinneApp


def main():
    """Main entry point for OPENCLI."""
    app = OrinneApp()
    try:
        app.run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
