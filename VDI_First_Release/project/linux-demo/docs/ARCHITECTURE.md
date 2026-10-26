# Architecture and report mapping

Source: the uploaded `IKT213_rapport_Gruppe2__2_.zip`, especially `kapitler/02-maalsetting.tex`, `03-losningsalternativer.tex`, `04-teori.tex`, `05-implementering.tex`, `kode/ta_bilder.py` and `figurer/NySystemArk.png`. The LaTeX filenames and visible chapter titles differ; this implementation follows the actual contents and the diagram.

| Diagram component | Python module | Responsibility |
|---|---|---|
| GUI | `vdi/gui.py` | One capture request; loading, picture/classification, explicit operator Pass/Reject, history and statistics |
| Main Controller | `vdi/main_controller.py` | Coordinates services, retains the ID, decides the automatic result and persists the operator's separate final choice |
| Picture Controller | `vdi/picture_controller.py` | Gets a camera frame or imported image, records acquisition metadata, prepares analysis/preview branches |
| Camera | `vdi/camera.py` | Applies the original script's camera controls and captures a frame; does not save images |
| Picture Saver | `vdi/picture_saver.py` | Persists initial pictures and final results through one database |
| Picture Inspector | `vdi/picture_inspector.py` | Runs OpenCV geometry and then the replaceable defect model; returns the same inspection ID |
| Database | `vdi/database.py` | Assigns unique integer IDs, stores images/metadata and confirms transaction commits |

The trained YOLO11n model has two **classes**, scratch and crack. It is not responsible for presence, product shape or calibrated dimensions. There is no need to add fake shape classes to the trained model or move its checks into the controller.

## Request sequence

1. The operator presses the capture button once. The GUI disables capture/decision buttons, shows Loading and calls `MainController.inspect(requires_operator_review=True)` with a camera request. There is no per-inspection input-image chooser or test-case selector. File imports remain a developer command-line option.
2. Main Controller calls Picture Controller, which acquires the original full-resolution frame and prepares grayscale/Laplace branches. Camera capture records its frame receipt time. An imported file retains unknown original capture time.
3. Main Controller calls Picture Saver. One transaction inserts a PENDING inspection row, receives SQLite's `lastrowid`, and inserts PNG image bytes for the original, gray and Laplace preview under that ID. That transaction commits **before** the inspector runs.
4. Main Controller sends the in-memory packet and ID to Picture Inspector. The original image does not need to be reloaded from storage. The geometry service detects an external contour, compares it to a good reference and measures it. Model inference only runs after all geometry checks pass.
5. Picture Inspector returns checks, measurements, detections, annotated pixels and the same ID. Main Controller verifies the ID and decides the automatic state.
6. Picture Saver updates the original row and stores the annotated image in one transaction. It cannot overwrite a completed automatic result. After commit, the GUI displays the model classification, automatic result and annotated picture, and enables Pass and Reject.
7. The operator chooses Pass or Reject. The GUI calls Main Controller, which calls Picture Saver to store `operator_decision` and its timestamp under the same ID. The automatic result and detections remain unchanged. After commit, capture becomes available for the next protector. Duplicate disposition writes are rejected.

`test_on_pc.py` injects an explicit simulated camera through `vdi/application.py`. Each capture automatically supplies the next test image and its corresponding placeholder-model scenario. The remaining controllers, checks, storage and GUI review flow are the same. Simulated captures are refused with a real inspection profile or a real-model backend. `main.py` defaults to the physical camera and real profile.

Dimensions are calculated from the same reliable contour used for shape comparison. A shape failure and size failure can both be reported, but the defect model is skipped when geometry fails or is incomplete.

All services are ordinary Python classes in one local application. No network service or second database is required. Only one worker runs a GUI inspection at a time. Worker messages cross a queue; Tk updates stay on the UI thread.

## State and persistence

The automatic `decision` field uses five states: `PENDING` means the image exists but no completed result has been committed; `PASS` requires passing presence, shape, dimensions and defects; `REJECT` means a configured product check failed; `INCOMPLETE` means prerequisites are missing; `ERROR` means the software/model could not complete normally.

The independent `operator_decision` is initially null, then becomes PASS or REJECT when the operator chooses. An operator can dispose of a protector even when the automatic result is ERROR or INCOMPLETE; the GUI explicitly identifies that as a manual disposition and retains the automatic failure. A saved operator choice is immutable through the application. Until a requested choice is saved, another GUI capture is blocked. Restarting restores the pending review, result and image. Legacy and headless records do not acquire a new review requirement retroactively.

A failure before acquisition/image storage produces a GUI error and no inspection row. A later model/analysis error is recorded under the original ID with the original image. If final storage fails, a confirmed PASS/REJECT is not returned. If the application is terminated during analysis, the PENDING row remains visible. It is never counted as PASS. There is no automatic recovery or retry of interrupted records in this version; start a new inspection after resolving the failure.

`elapsed_ms` measures acquisition, preprocessing, initial persistence and analysis, ending before final persistence. It is not claimed as pure model inference time or full end-to-end response latency.

`inspections` stores ID, timestamps, source/camera metadata, demo flag, automatic decision/reason, timing, configuration snapshot, image quality metrics, checks, dimensions, defect boxes and confidence scores. Schema version 2 adds `requires_operator_review`, `operator_decision` and `operator_decided_at`. Version 1 upgrades transactionally without replacing old rows or image bytes. Reference and real model SHA-256 hashes identify their content in successful checks. `images` stores original, gray, Laplace-preview and annotated images linked by `inspection_id`.

Statistics and CSV export distinguish automatic results from operator decisions. Rejected-image export uses the operator's rejection when review was requested; unreviewed legacy/headless records retain the original automatic rejection behavior. Awaiting choices do not count as operator passes or rejects.

PNG preserves the decoded original pixels losslessly; imported JPEG source bitstreams and EXIF are not preserved as original files. Everything is in a **single SQLite database file**, including the PNG image bytes. The code does not keep a second loose-image storage tree. This is a concrete implementation of the report's one-database design, not a change to the controller sequence. Exports produce user-selected CSV/ZIP files.

All captured/imported images, including passing products, are retained to match the save-before-analysis design. Storage therefore grows over time. Back up the SQLite file while the application is closed, or use SQLite's backup API. Copy configuration, content-addressed references and model weights too when transferring the complete working system.

## Functional requirements

| Requirement | Implementation | Validation needed on the actual rig |
|---|---|---|
| FR1 load image/errors | Decode with OpenCV, supported extensions and corrupt-file checks, GUI errors | Actual file inputs/camera |
| FR2 detect protector | Closed external contour, area checks, ambiguity/boundary checks | Empty tray, reflections, all placements |
| FR3 expected shape | Reference contour + Hu distance + fill ratio + aspect ratio | Wrong-model and missing-piece validation sets |
| FR4 calibrated width/height | Rotated minimum-area rectangle, mm-per-pixel scale, inclusive tolerances | Real calibration, distortion/plane assumptions |
| FR5 scratch/crack | Controlled placeholder and existing Ultralytics detector adapter | Actual best.pt, class mapping, precision/recall |
| FR6 final decision | Main Controller automatic rules; explicit operator disposition saved separately; real placeholder/missing checks cannot automatically pass | Complete rig acceptance tests |
| FR7 metadata/statistics | Same database ID before/after analysis, timestamps, checks, images, category counts, CSV/ZIP | Storage capacity and real deployment |
| FR8 GUI | One-button capture/loading/results/picture; operator Pass/Reject; history/statistics | User testing on PC and Jetson display |

The implemented defect classes are scratch and crack, as specified in the current report. Confidence and geometry thresholds are starting configuration values, not empirically established performance claims.

## Technical sources checked

- [OpenCV contour features](https://docs.opencv.org/4.x/dd/d49/tutorial_py_contour_features.html): contours and rotated minimum-area rectangles.
- [OpenCV shape comparison](https://docs.opencv.org/4.x/d5/d45/tutorial_py_contours_more_functions.html): Hu-moment shape matching and its comparison score.
- [Ultralytics prediction](https://docs.ultralytics.com/modes/predict/): BGR array input, confidence/IoU options and result boxes.
- [Ultralytics result API](https://docs.ultralytics.com/reference/engine/results/): original-pixel boxes, class IDs and confidence.
- [Python Tkinter threading model](https://docs.python.org/3/library/tkinter.html#threading-model): GUI event loop and threading constraints.

The report takes precedence for the project's chosen model and requirements; current examples for newer YOLO models do not change the project to a different model.
