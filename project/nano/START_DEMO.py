"""Explicit software simulation; no physical camera or real-model dependency."""
import sys
from main import main

if __name__ == "__main__":
    sys.exit(main(["--test-camera"] + sys.argv[1:]))
