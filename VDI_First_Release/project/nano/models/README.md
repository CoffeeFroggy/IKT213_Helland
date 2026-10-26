# Supplied trained models

`best.pt` is the uploaded scratch/crack YOLO detector; `shape_model.pth` is the uploaded three-class MobileNetV3-small shape/presence classifier. Both files are included unchanged from `VDI_repository.zip`. `checksums.json` records their SHA-256 identities.

The shape adapter preserves the supplied checkpoint preprocessing and provisional thresholds. The detector preserves confidence 0.25, IoU 0.75, image size 1024 and scratch-only duplicate suppression at IoU 0.70. Both use CPU by default for the PC test.

No millimetre calibration is embedded in either model.
