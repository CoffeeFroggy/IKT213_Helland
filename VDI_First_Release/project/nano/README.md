# Visual Defect Inspector: Jetson Nano

Extract this ZIP on the Nano. Open a terminal in the extracted folder and run:

```bash
bash START_NANO.sh
```

The first start installs missing Ubuntu camera/GUI packages and creates `.nano-venv`. It may ask for your sudo password. Connect the Razer Kiyo Pro and run on the Nano desktop with its monitor connected. The setup checks both trained models before opening the GUI. Later starts reuse that environment.

This build sets `OPENBLAS_CORETYPE=ARMV8` before importing NumPy on ARM64, avoiding the known NumPy 1.19.5/OpenBLAS illegal-instruction crash on the Nano. For an older extracted copy, run `OPENBLAS_CORETYPE=ARMV8 bash START_NANO.sh` in its terminal.

In PyCharm, run `START_GUI.py` using the project's `.nano-venv/bin/python` interpreter after setup. `config.py` contains configuration helpers and does not open the GUI. Setting an environment variable in PyCharm's Terminal does not change a green-button Run configuration; the corrected package sets the workaround in Python too. `INSTALL_MODELS.sh` only installs/checks dependencies; `START_NANO.sh` installs if needed and then opens the GUI.

The supplied MobileNet shape model and YOLO11 scratch/crack detector are included as ONNX files. This version runs both on the CPU through ONNX Runtime. It does not require PyTorch, torchvision or Ultralytics on the Nano. Original trained weight files are also preserved.

Original Nano / JetPack 4 / system Python 3.6 uses the included ARM64 wheels. OpenCV and Tk are inherited from Ubuntu packages to preserve V4L2 camera support. The Python model packages can install offline; missing Ubuntu packages still need apt access. Python 3.8-3.12 installations use pip to obtain the corresponding runtime.

Camera settings remain 1920x1080 YUYV, focus 157, exposure 2047 and gain 0. The camera is found by its stable Kiyo Pro device path. Edit `config/inspection.json` only if your camera/settings differ.

For a model check without opening the GUI:

```bash
.nano-venv/bin/python tools/check_models.py
```

The original ROI, RGB conversion, padding, normalization, trained classes and confidence thresholds are preserved. The detector export uses 576x1024, matching the original detector's rectangular preprocessing for 1920x1080 images.

Without physical size calibration, the application can test the real shape and defect models but reports INCOMPLETE rather than claiming a full automatic PASS. Use the GUI calibration workflow for millimetre measurements.

The model outputs and software pipeline have been checked on the included real examples in the build environment. The physical Nano, camera exposure, GPU performance and installation on your own board still require your on-device test.

Do not run the old PC installation instructions. `START_HERE.sh` and `INSTALL_MODELS.sh` now call the Nano scripts.
