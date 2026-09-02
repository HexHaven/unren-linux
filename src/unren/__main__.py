"""Allow ``python -m unren`` as an alternative to the ``unren`` entry point."""

from unren.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
