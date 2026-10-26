"""Construct the same inspection pipeline with a physical or explicit test camera."""
from .config import ConfigurationError
from .demo import TestCamera
from .main_controller import MainController
from .picture_controller import PictureController


def create_controller(settings, test_camera=False):
    camera = None
    if test_camera:
        if not settings.data["demo"] or settings.data["model"]["backend"] != "placeholder":
            raise ConfigurationError("The test camera requires the test profile and placeholder model.")
        camera = TestCamera()
    return MainController(settings, picture_controller=PictureController(settings, camera=camera))
