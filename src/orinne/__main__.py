"""ORINNE entry point."""

import sys
from orinne.tui.app import OrinneApp


def main():
    """Main entry point for ORINNE."""
    app = OrinneApp()
    try:
        app.run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
