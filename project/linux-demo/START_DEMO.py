"""Run this file in PyCharm to test the one-button workflow without the camera rig."""
import sys

from main import main


if __name__ == "__main__":
    sys.exit(main(["--test-camera"] + sys.argv[1:]))
