"""Three-class shape classifier. Never treats a failed prediction as an empty box."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
from .config import ROOT
import hashlib

CLASS_NAMES = ["correct_shape", "no_protector", "shape_defect"]
MODEL_FILE = ROOT / "models" / "shape_model.pth"
PREPROCESS = dict(size=448, roi=[0.25, 0.0, 0.80, 1.0], frame_ratio=1920/1080,
                  mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
THRESHOLDS = dict(correct_shape=0.90, shape_defect=0.85, no_protector=0.90)
MARGIN = 0.20


def prepare_pil(image, config):
    """Same fixed field of view and aspect-preserving resize at train and inference."""
    image = image.convert("RGB")
    w, h = image.size
    if abs(w / h / config["frame_ratio"] - 1) > 0.02:
        raise ValueError("Bildets sideforhold avviker fra treningsoppsettet.")
    x1, y1, x2, y2 = config["roi"]
    crop = image.crop((round(w*x1), round(h*y1), round(w*x2), round(h*y2)))
    return ImageOps.pad(crop, (config["size"], config["size"]),
                        method=getattr(Image, "Resampling", Image).BILINEAR, color=(114,114,114))


def decide_shape(probabilities, thresholds=THRESHOLDS, margin=MARGIN):
    if set(probabilities) != set(CLASS_NAMES):
        raise ValueError("Uventede formklasser")
    if any(not np.isfinite(v) or v < 0 or v > 1 for v in probabilities.values()):
        raise ValueError("Ugyldige klasseverdier")
    if abs(sum(probabilities.values()) - 1) > 0.001:
        raise ValueError("Klasseverdiene summerer ikke til 1")
    ordered = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
    name, confidence = ordered[0]
    gap = confidence - ordered[1][1]
    confident = confidence >= thresholds[name] and gap >= margin
    return dict(status=name if confident else "uncertain", predicted_class=name,
                confidence=confidence, margin=gap, probabilities=probabilities,
                reason="classified" if confident else "low_confidence_or_margin",
                thresholds=dict(thresholds), required_margin=margin,
                provisional_thresholds=True, method="mobilenet_v3_small_shape")


class ShapeClassifier:
    def __init__(self, model_path=MODEL_FILE, device="cpu"):
        self.requested_device = device
        self.path = Path(model_path)
        self.model = None
        self.config = None

    def classify(self, image):
        if not self.path.is_file():
            return dict(status="unavailable", reason="shape_model_missing", model=str(self.path))
        try:
            import torch
            from torchvision.models import mobilenet_v3_small
            if self.model is None:
                if self.requested_device == "cpu":
                    torch.set_num_threads(min(torch.get_num_threads(), 4))
                checkpoint = torch.load(self.path, map_location="cpu", weights_only=True)
                if checkpoint.get("format") != "vdi_shape_mobilenet_v1" or checkpoint["classes"] != CLASS_NAMES:
                    raise ValueError("Feil format eller klasser i formmodellen")
                self.device = torch.device(self.requested_device)
                model = mobilenet_v3_small(weights=None)
                model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, len(CLASS_NAMES))
                model.load_state_dict(checkpoint["state_dict"])
                model.to(self.device).eval()
                self.config = checkpoint["preprocess"]
                self.model = model
                self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
            # OpenCV input is BGR; the network receives RGB.
            prepared = prepare_pil(Image.fromarray(image[:, :, ::-1]), self.config)
            array = np.asarray(prepared).astype(np.float32) / 255.0
            array = (array - np.array(self.config["mean"], np.float32)) / np.array(self.config["std"], np.float32)
            tensor = torch.from_numpy(array.transpose(2,0,1).copy()).unsqueeze(0).to(self.device)
            with torch.inference_mode():
                values = torch.softmax(self.model(tensor), dim=1)[0].cpu().tolist()
            record = decide_shape(dict(zip(CLASS_NAMES, map(float, values))))
            record.update(model=str(self.path), device=str(self.device),
                          model_sha256=self.sha256, preprocess=self.config)
            return record
        except Exception as exc:
            return dict(status="uncertain", reason="shape_analysis_error", detail=str(exc), model=str(self.path))
