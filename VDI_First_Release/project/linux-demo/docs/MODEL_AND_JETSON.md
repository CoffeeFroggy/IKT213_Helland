# Model integration on the PC, then Jetson deployment

## Model files and facts still needed

Get the actual trained `best.pt` from your teammate, plus the exact Ultralytics, PyTorch and Python versions used for training. Confirm the class mapping (`scratch: 0`, `crack: 1`), whether input was original colour, and the confidence/IoU settings selected on the validation set.

The report gives YOLO11n, input size 1024, two detection classes and `best.pt`. It does not include those weights. It does not establish production thresholds or guarantee a trained model will run on the Nano's current software.

## PC model test

1. Finish the geometry calibration described in the README.
2. Copy the group's trained weights into `models/best.pt`.
3. Use the training environment's Ultralytics version where possible. Otherwise the optional PC dependency file is a starting range, not a reproducibility lock.
4. Avoid keeping both `opencv-python` and `opencv-python-headless` in the same environment. Ultralytics depends on `opencv-python`. If the initial demo environment used the headless wheel, the PC switch can be:

```bash
python -m pip uninstall opencv-python-headless
python -m pip install -r requirements-model-pc.txt
```

If your existing environment already uses `opencv-python` or Conda's OpenCV, keep a working installation and resolve package versions deliberately. Do not remove a training environment's dependencies blindly. Check `python -m pip check` afterwards.

5. In `config/inspection.json`, change only the relevant model values:

```json
"model": {
  "backend": "ultralytics",
  "weights": "models/best.pt",
  "input": "original_bgr",
  "image_size": 1024,
  "confidence": 0.25,
  "iou": 0.45,
  "device": "cpu"
}
```

Keep `demo` false. The values 0.25/0.45 are provisional defaults. Use the group's validated values when available. CPU is an explicit PC starting point; selecting `"0"` for a CUDA GPU requires a compatible PyTorch installation.

6. Run `python main.py`, press the capture button and inspect the actual camera picture and defect overlays. Choose Pass or Reject after each completed analysis. Test no defects, scratch only, crack only, and both. For saved validation images, use `python main.py --image /absolute/path/image.png` from a terminal. Compare boxes and labels against annotations. Evaluate the independent test set only after thresholds are fixed.

The adapter loads a local model only; it does not download substitute pretrained weights. Incorrect classes, unsupported model tasks, missing files or invalid results produce ERROR. Empty valid detections mean the model found no supported defect above threshold, not a guarantee that the physical product has no defect.

## What transfers to the Jetson

The controllers, saver, database, GUI, OpenCV geometry and placeholder are separate from the model backend. Copy the project folder, calibrated profile, `assets/references/`, trained weights, and optionally the closed database. Recalibrate if camera geometry, resolution, focus or product plane changes. Model engines must match the target runtime/hardware.

Before installing model packages on the Jetson, run:

```bash
python3 tools/jetson_info.py
```

This reads the actual device model, L4T information, Python version and installed package versions. **Do not copy your PC Conda/venv directory to ARM64.** Create/use a Jetson environment with matching packages instead.

The original Jetson Nano and the Jetson Orin Nano are different devices. Official Ultralytics deployment documentation lists the original Nano under JetPack 4, while newer Orin devices use later stacks. NVIDIA's PyTorch wheels are tied to the JetPack/Python compatibility matrix. Therefore an unconditional `pip install` of current PC model dependencies on the original Nano is not a supported deployment plan.

The core app avoids dataclasses, modern union annotations and other Python 3.7+ syntax; Python 3.6 syntax parsing is checked. Running the core demo on a legacy JetPack environment should use the environment's working OpenCV/NumPy/Tk/Pillow packages. That still requires an actual on-device smoke test. Do not install the PC requirements file into the Nano's system Python. For example, the pinned OpenCV PC wheel requires a newer Python than a typical legacy system installation.

For the trained detector, choose a verified JetPack 4-compatible Ultralytics/PyTorch environment or supported Jetson container, or implement/test an exported backend appropriate for the actual runtime. This project currently implements the Ultralytics adapter; it does **not** claim a tested standalone ONNX/TensorRT backend. Do not copy a TensorRT engine built for the PC GPU and assume it is portable.

Keeping the application/model boundary separate means such a backend can be added through the `predict(image, scenario)` interface without redesigning the GUI or persistence flow. First establish a correct PC result, then compare the Jetson's outputs on the same images before evaluating speed.

## Camera integration on the Nano

Run with a desktop display for the GUI. Confirm the stable device path and the actual control names with `v4l2-ctl --list-devices` and `v4l2-ctl -d DEVICE --list-ctrls` before capture. Use the profile's exact full-resolution mode for the saved calibration. The application releases the camera after each requested capture; other camera tools should be closed while testing.

## Official deployment references

- [Ultralytics on NVIDIA Jetson](https://docs.ultralytics.com/guides/nvidia-jetson/)
- [NVIDIA PyTorch installation for Jetson](https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/index.html)
- [NVIDIA Jetson Linux R32.7.6 / JetPack 4.6.6](https://developer.nvidia.com/embedded/linux-tegra-r3276)
- [Ultralytics installation requirements](https://docs.ultralytics.com/quickstart/)

Documentation checked during implementation on 25 October 2026. Use the actual device information and the applicable compatibility matrix when installing; avoid blindly following examples for Orin/Thor on the original Nano.
