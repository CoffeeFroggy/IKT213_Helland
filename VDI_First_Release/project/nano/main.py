"""GUI by default; optional headless entry point for testing and integration."""
import argparse
import json
import sys

from vdi.config import ROOT, load_settings
from vdi.application import create_controller
from vdi.demo import generate_demo_assets


def main(argv=None):
    parser = argparse.ArgumentParser(description="Visual Defect Inspector")
    parser.add_argument("--config", help="Profile path. Default: config/inspection.json; demo.json with --test-camera")
    parser.add_argument("--test-camera", action="store_true", help="Explicit PC testing with an automatic simulated camera")
    parser.add_argument("--image", help="Inspect this image without opening a GUI")
    parser.add_argument("--capture", action="store_true", help="Capture and inspect without a GUI")
    parser.add_argument("--scenario", choices=["clean", "scratch", "crack", "both", "model_error"], default="clean")
    parser.add_argument("--db", help="Override the database path, for isolated software tests")
    args = parser.parse_args(argv)
    if args.image and args.capture:
        parser.error("Use either --image or --capture.")
    try:
        default_profile = ROOT / "config" / ("demo.json" if args.test_camera else "inspection.json")
        settings = load_settings(args.config or default_profile)
        if args.db:
            settings.data["database"] = args.db
        if settings.data["demo"]:
            generate_demo_assets()
        controller = create_controller(settings, test_camera=args.test_camera)
        if args.image or args.capture:
            result = controller.inspect(args.image, args.scenario)
            result.pop("annotated", None)
            print(json.dumps(result, indent=2))
            return 2 if result["decision"] in ("ERROR", "INCOMPLETE") else 0
        from vdi.gui import launch
        launch(settings, controller=controller)
        return 0
    except Exception as exc:
        print("VDI: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
