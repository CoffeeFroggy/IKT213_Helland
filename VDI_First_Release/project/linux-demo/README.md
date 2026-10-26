# Visual Defect Inspector - IKT213 Group 2

One press captures the next protector, saves the picture, checks geometry, runs the defect model and displays the result with its picture. While this runs, the GUI says **Loading...** and shows progress. The operator then presses **Pass screen protector** or **Reject screen protector**. The next capture becomes available after that choice is saved.

The model's output, the combined automatic inspection result and the operator's final decision are retained separately. A manual choice never overwrites the automatic result. The model described in the report detects **scratch (class 0)** and **crack (class 1)**. Presence, shape, width and height are separate OpenCV checks.

## Update your existing PyCharm project

Your existing working `vdi` Conda interpreter can be reused. You do not need to create another environment or install model packages for the PC test.

1. Close the running inspection window.
2. Extract this ZIP into a separate folder.
3. Inside its `visual_defect_inspector` folder, copy **`main.py`**, **`test_on_pc.py`** and the entire **`vdi` folder** into your existing project. Replace matching source files. Keep your existing `config`, `data`, `models`, `assets/references` and PyCharm settings.
4. In PyCharm, right-click **`test_on_pc.py`** and select **Run**. Use the same interpreter that already ran the previous GUI. For the setup used in this chat, that is `/home/alex/anaconda3/envs/vdi/bin/python`.
5. Follow the PC test below. The existing database upgrades automatically; old IDs, pictures and results are retained.

Your project folder from the earlier setup was:

```text
/home/alex/Ikt213 Prosjekt/Visual_Defect_Inspector_PC/visual_defect_inspector
```

## Test the complete operator workflow on your PC

Run `test_on_pc.py` in PyCharm, or run this from the project terminal:

```bash
python test_on_pc.py
```

A yellow **TEST MODE** banner identifies the simulated camera and placeholder defect model. No camera, model weights, GPU or internet is needed.

1. Press **Take picture and analyze next screen protector** once.
2. The GUI shows **Loading...** and progress. Capture and decision buttons are disabled during processing.
3. The picture and result appear automatically. The first new test session should show **TEST: No defect detected**, automatic **PASS**, and artificial measurements of approximately **70 x 150 mm**.
4. Press **Pass screen protector** or **Reject screen protector**. Either choice is allowed; this is the operator's decision. A saved confirmation appears. The original automatic result stays unchanged.
5. Press the capture button again. This time a scratch case appears automatically. Continue with the remaining cases if desired.
6. Close the app after an analysis without choosing Pass or Reject. Reopen it: the pending picture and choice are restored. Finish that choice before the next capture.

There is no input-image chooser or test-case selector in the inspection screen. The test camera advances automatically through these cases:

| Capture in a new test session | Automatic inspection | Model classification |
|---|---|---|
| 1. Clean protector | PASS | No defect detected |
| 2. Scratch | REJECT | Scratch |
| 3. Crack | REJECT | Crack |
| 4. Scratch and crack | REJECT | Scratch + Crack |
| 5. Empty tray | REJECT | Not run |
| 6. Wrong shape | REJECT | Not run |
| 7. Missing piece | REJECT | Not run |
| 8. Wrong dimensions | REJECT | Not run |
| 9. Rotated protector | PASS | No defect detected |
| 10. Model failure | ERROR | Unavailable |

The sequence repeats after case 10 and starts from case 1 when the application is restarted. If a previous result awaits review, it appears before a new capture. The OpenCV checks run on actual synthetic image pixels. Only the defect outputs and camera source are simulated. Placeholder confidence values are test constants, not measured accuracy.

The **History** tab shows each automatic result and operator choice. **Statistics** shows both sets of counts and pass rates. **Export results CSV** includes both decisions. **Export rejected images ZIP** follows the operator's rejection for GUI records. Older records without an operator-review step retain their original automatic rejection behavior.

Test records use `data/demo.sqlite3`; real records use `data/inspections.sqlite3`. The download contains no prepopulated database. All captured pictures and results are stored in SQLite under the same inspection ID.

## Use the physical camera

Run **`main.py`** in PyCharm:

```bash
python main.py
```

This starts the same GUI using `config/inspection.json` and the physical camera. The script captures directly when the operator presses the button; it does not require a separate photography script or manual image import. Camera resolution and controls come from the profile.

The supplied real profile intentionally has no invented calibration values and uses the placeholder backend until your actual trained model is available. Missing calibration or a real-mode placeholder prevents an automatic PASS. You can test the physical capture path, but the complete inspection needs calibration and the real model.

Before connecting the rig, review the device path and settings in `config/inspection.json`. The initial profile follows the report's Razer Kiyo Pro settings. On Linux, `v4l2-ctl` must be available to apply/read back the fixed camera controls. The camera is released after each capture.

## One-time geometry calibration

Open **Setup > Calibration...** in the physical-camera GUI. This is setup work, separate from the repeated inspection workflow.

1. Load a full-resolution image of a known good protector from the actual camera setup.
2. Check that the green contour follows the entire protector edge. Adjust the outline method, threshold, closing kernel or ROI if necessary and press **Update outline**. ROI is `[left, top, right, bottom]` as fractions; `0,0,1,1` uses the whole image.
3. Click two points a known physical distance apart at the glass plane. Enter that distance in millimeters. The tool calculates `mm_per_pixel = known_mm / distance_px`.
4. Enter the actual expected width, height and tolerances. Width is the shorter side. The report did not supply these measurements, so real values must be measured.
5. Confirm the contour checkbox and save, then restart `main.py`.
6. Validate additional known sizes, placements, rotations, wrong-model protectors and missing pieces. Tune thresholds on validation data before evaluating the independent test set.

Calibration saves a content-addressed reference PNG in `assets/references/`, the profile and a backup of its previous contents. Changing camera resolution invalidates the stored calibration. A fixed plane, stable lighting and appropriate distortion/perspective control are needed for meaningful millimeter measurements.

## Fresh installation on another Linux PC

Prefer the working environment you already have. For a fresh Conda setup:

```bash
conda create -n vdi python=3.12 pip tk -y
conda activate vdi
python -m pip install -r requirements.txt
python tools/check_environment.py
python test_on_pc.py
```

Select that environment's Python executable in PyCharm. With the `/home/alex/anaconda3` installation used earlier, the executable is `/home/alex/anaconda3/envs/vdi/bin/python`.

The core GUI uses Tk. Only one OpenCV distribution should be installed in a given environment. The optional trained-model dependencies are separate; do not install them just to run the placeholder test. Ubuntu system-Python installations may need `python3-tk` and `python3-venv` through the package manager.

## Model and Jetson integration

See [docs/MODEL_AND_JETSON.md](docs/MODEL_AND_JETSON.md) for the model adapter and transfer plan. Add the group's actual `best.pt` and a compatible runtime, then change `model.backend` to `ultralytics` in the real profile. The operator's capture/loading/result/Pass-or-Reject workflow stays the same.

The original Nano needs a compatible JetPack/Python/model runtime. Copy the application and configuration to it, not your PC Conda directory. Real hardware, model accuracy and Jetson performance still need validation on your rig.

## Developer checks

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Actual Tk tests run when a desktop/X display is available; otherwise they are explicitly skipped. Headless single-image inspection remains available for developer testing, without changing the operator GUI:

```bash
python test_on_pc.py --capture --db /tmp/vdi-software-test.sqlite3
python main.py --image /absolute/path/image.png
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for report mapping and persistence, and [docs/VALIDATION.md](docs/VALIDATION.md) for test evidence and remaining rig checks.
