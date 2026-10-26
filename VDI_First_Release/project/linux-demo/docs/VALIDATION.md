# Validation record

Verified on 25 October 2026 in a Linux x86_64 environment:

- Python 3.12.14, OpenCV 4.10.0, NumPy 2.3.5, Pillow 12.3.0, SQLite and Tkinter.
- **64 automated tests passed** in the final run, including **8 actual Tk GUI tests** using a virtual display (8.93 seconds). This is software validation, not a model-performance benchmark.
- All 19 application/helper modules parsed with Python 3.6 syntax. This is a static check, not execution under Python 3.6.
- The capture/loading, clean-result, scratch-result and 1080 x 688 window states were rendered and visually inspected. Capture and decision controls remain visible. The calibration screen has also been rendered; its save control is checked by an actual Tk test.
- A clean extraction and headless command-line startup were checked separately to verify the package and project-relative paths.

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
| GUI | Loading/disabled controls; automatic picture/classification; both operator choices; history/statistics; capture retry; choice-storage failure/retry; restart with a pending choice; model failure; controls fit a smaller window; calibration save |

## What still needs the actual project hardware/data

The report ZIP does not contain trained model weights, full-resolution source images with a physical scale, actual nominal dimensions/tolerances, or the target Jetson software environment. The camera and physical Nano are not attached here. Therefore this package establishes an integration-tested application and a working simulation, not measured defect-detection accuracy or verified on-device performance.

1. Verify reliable outlines on empty, good, wrong-model and missing-piece Blackbox images. Tune segmentation and shape thresholds on a validation set. Investigate reflections and ambiguous contours.
2. Measure the physical reference and enter nominal dimensions/tolerances. Check scale over the inspection plane and rotations. Assess lens distortion and perspective before claiming the required millimeter precision.
3. Integrate the actual trained `best.pt`, match its training preprocessing/runtime, and measure class-specific precision, recall, false positives and false negatives against annotations.
4. Capture on the real Razer camera through the GUI, verify settings and white balance, and compare image distributions with the training data.
5. Inspect the actual Jetson/JetPack/Python packages, establish a compatible model runtime, and compare output on the same files before performance tests.
6. Run the entire sequence on the rig, including restart/history, retained images, unavailable camera, and storage-error handling. Document expected/observed outcomes against FR1-FR8.

Demo cases and real inspections use different databases and flags. Software-test PASS results must not be reported as the trained model's accuracy or the rig's acceptance rate.
