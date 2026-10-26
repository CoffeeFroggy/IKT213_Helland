# Validation record

Verified on 26 October 2026 in a Linux x86_64 environment:

- Python 3.12.14, OpenCV 4.10.0, NumPy 2.3.5, Pillow 12.3.0, SQLite and Tkinter.
- **88 automated tests passed** in the final run, including **20 actual Tk GUI tests** using a virtual display (28.51 seconds). This is software validation, not a model-performance benchmark.
- All 25 application/helper modules parsed with Python 3.6 syntax. This is a static check, not execution under Python 3.6.
- The welcome, capture/loading, clean-result, scratch-result and 1080 x 688 window states were rendered and visually inspected. Capture and decision controls remain visible. The calibration screen has also been rendered; its save control is checked by an actual Tk test.
- Release 0.4.0 integrates the actual uploaded shape and defect weights. SHA-256 hashes match the supplied manifest. CPU PyTorch 2.9.1+cpu, torchvision 0.24.1+cpu and Ultralytics 8.4.182 ran the four provided real images, reproducing correct-shape/clean, wrong-shape, empty-box and correct-shape/three-scratches-plus-one-crack outputs. The clean image remains INCOMPLETE overall until dimensions are calibrated.
- Release 0.3.1 removes all inspection scrolling, bundles smooth proportional fonts, enlarges headings and values, uses a divided comparison grid, colors every main button with a common outline, and paginates history.
- Release 0.3.0 adds the welcome menu, inspection workspace, history page, Statistics/User Guide placeholders, rounded buttons, and comparisons using each inspection's saved settings.
- Release 0.2.1 replaces the ambiguous `test_on_pc.py` launcher with `START_GUI.py` and adds `START_HERE.sh`, which runs the existing PC Python environment directly.
- A clean ZIP extraction, direct GUI startup and headless capture through the shell launcher were checked from a folder containing spaces and from an unrelated working directory. The default Conda-interpreter lookup was exercised with an isolated test home directory.

## What the tests cover

| Area | Evidence |
|---|---|
| End-to-end decisions | Clean/rotated, scratch, crack, both, absent, wrong shape, missing piece, wrong size and model failure |
| Architecture sequence | An independent database connection sees the PENDING row and saved original before the inspector runs; database ID is retained |
| Failures | Invalid/empty files, missing reference/weights, storage failures, invalid result transitions, incompatible schema, concurrent request prevention |
| Calibration | Known synthetic dimensions, inclusive tolerances, missing scale, changed resolution, GUI two-point scale and saved profile |
| Model boundary | Original BGR pixels preserved; class mapping, confidence, IoU, image size and box parsing checked with a fake Ultralytics API |
| Camera boundary | Missing device, control failures, resolution checks and release on success/failure checked with mocked hardware |
| Storage/history | Original PNG decodes to identical pixels; unique IDs; model errors retained; mode-separated statistics/exports; version-1 database migration retains IDs, image bytes and results |
| Operator disposition | Capture blocked until review; immutable, timestamped Pass/Reject; automatic results preserved when overridden; separate rates and operator-based rejected-image export; pending choice survives restart |
| Automated test camera | All ten cases and wraparound run through capture without a file/case selection; simulated frames refused in real mode or with a real-model backend |
| GUI | No nested scrolling or scrollable text boxes; full compact-layout visibility for normal, absent, wrong-shape/size, model-error and incomplete-calibration results; filled button surfaces and consistent outlines; bundled FreeType proportional-font check; history pagination; welcome/menu navigation, placeholder destinations, history navigation with unfinished review preserved, real mouse/keyboard activation of rounded buttons, expected/measured comparisons from saved configuration; loading/disabled controls; automatic picture/classification; both operator choices; history/statistics; capture retry; choice-storage failure/retry; restart with a pending choice; model failure; controls fit a smaller window; calibration save |

## What still needs the actual project hardware/data

The uploaded VDI_repository.zip now supplies actual trained weights and four original example images. Both models have been executed on those real images and through the capture-button GUI pipeline with a mocked camera interface delivering one real image. Physical scale, actual nominal dimensions/tolerances and the target Jetson runtime remain unavailable. No physical camera or Nano is attached here. These checks verify model integration, not independent accuracy, on-rig camera behavior or Nano performance.

1. Verify reliable outlines on empty, good, wrong-model and missing-piece Blackbox images. Tune segmentation and shape thresholds on a validation set. Investigate reflections and ambiguous contours.
2. Measure the physical reference and enter nominal dimensions/tolerances. Check scale over the inspection plane and rotations. Assess lens distortion and perspective before claiming the required millimeter precision.
3. Evaluate the integrated shape and scratch/crack models on an independent annotated set. Measure class-specific precision/recall and false positives/negatives. The four supplied examples are regression checks, not an independent accuracy study.
4. Capture on the real Razer camera through the GUI, verify settings and white balance, and compare image distributions with the training data.
5. Inspect the actual Jetson/JetPack/Python packages, establish a compatible model runtime, and compare output on the same files before performance tests.
6. Run the entire sequence on the rig, including restart/history, retained images, unavailable camera, and storage-error handling. Document expected/observed outcomes against FR1-FR8.

Demo cases and real inspections use different databases and flags. Software-test PASS results must not be reported as the trained model's accuracy or the rig's acceptance rate.
