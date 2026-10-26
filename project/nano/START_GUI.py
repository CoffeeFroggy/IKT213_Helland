"""Start physical inspection with the camera and the trained models. This is an application launcher, not a test file."""
import sys

from main import main


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
