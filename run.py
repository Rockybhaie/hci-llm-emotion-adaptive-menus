"""Entry point. Examples:

    python run.py check
    python run.py preview --group G2 --menu M5
    python run.py session --group G2 --participant P04
    python run.py session --group G1 --participant P99 --fast --pilot
    python run.py export
"""

import sys

for stream in (sys.stdout, sys.stderr):      # Windows consoles default to cp1252
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from hci.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
