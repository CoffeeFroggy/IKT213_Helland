"""CPU inference for Jetson Nano, using the group's exported trained models."""
import ast
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .defect_model import filter_scratch_duplicates
from .shape_classifier import CLASS_NAMES, prepare_pil, decide_shape


def session_for(path):
    try:
        import onnxruntime as ort
    except ImportError:
        raise RuntimeError('ONNX Runtime is missing. Run bash SETUP_NANO.sh first.')
    path = Path(path)
    if not path.is_file():
        raise RuntimeError('Trained model is missing: %s' % path)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=options,
                               providers=['CPUExecutionProvider'])


def nms(boxes, scores, classes, threshold, limit=300):
    order = np.argsort(-scores, kind='stable')
    kept = []
    while len(order) and len(kept) < limit:
        current = int(order[0])
        kept.append(current)
        order = order[1:]
        if not len(order):
            break
        other = boxes[order]
        intersection = np.maximum(0, np.minimum(boxes[current, 2:], other[:, 2:]) -
                                  np.maximum(boxes[current, :2], other[:, :2])).prod(axis=1)
        area = np.maximum(0, boxes[current, 2:] - boxes[current, :2]).prod()
        areas = np.maximum(0, other[:, 2:] - other[:, :2]).prod(axis=1)
        overlap = intersection / np.maximum(area + areas - intersection, 1e-12)
        order = order[(classes[order] != classes[current]) | (overlap <= threshold)]
    return kept


class OnnxDefectModel:
    is_placeholder = False

    def __init__(self, settings):
        self.settings = settings
        self._session = None
        self.name = 'onnxruntime_cpu: ' + settings.data['model']['weights']
        self.sha256 = None

    def _load(self):
        if self._session is not None:
            return
        path = self.settings.resolve(self.settings.data['model']['weights'])
        runtime = session_for(path)
        metadata = runtime.get_modelmeta().custom_metadata_map
        names = ast.literal_eval(metadata.get('names', '{}'))
        if names != {0: 'scratch', 1: 'crack'}:
            raise RuntimeError('Wrong detector classes: %s' % names)
        self._input = runtime.get_inputs()[0]
        if len(self._input.shape) != 4 or self._input.shape[:2] != [1, 3]:
            raise RuntimeError('Expected one fixed RGB detector input.')
        self.height, self.width = map(int, self._input.shape[2:])
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self._session = runtime

    def predict(self, image, scenario=None):
        self._load()
        config = self.settings.data['model']
        if config['image_size'] != max(self.height, self.width):
            raise ValueError('Configured detector size differs from the bundled model export.')
        h, w = image.shape[:2]
        ratio = min(self.width / w, self.height / h)
        resized_w, resized_h = int(round(w * ratio)), int(round(h * ratio))
        left = int(round((self.width - resized_w) / 2 - .1))
        top = int(round((self.height - resized_h) / 2 - .1))
        resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
        padded = np.full((self.height, self.width, 3), 114, dtype=np.uint8)
        padded[top:top + resized_h, left:left + resized_w] = resized
        tensor = np.ascontiguousarray(padded[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32) / 255.
        output = self._session.run(None, {self._input.name: tensor})[0]
        if output.ndim != 3 or output.shape[:2] != (1, 6) or not np.isfinite(output).all():
            raise RuntimeError('Detector returned an unsupported or invalid output.')
        rows = output[0].T
        classes = rows[:, 4:].argmax(axis=1)
        scores = rows[np.arange(len(rows)), classes + 4]
        selected = scores >= config['confidence']
        rows, scores, classes = rows[selected], scores[selected], classes[selected]
        boxes = np.empty((len(rows), 4), dtype=np.float32)
        boxes[:, :2] = rows[:, :2] - rows[:, 2:4] / 2
        boxes[:, 2:] = rows[:, :2] + rows[:, 2:4] / 2
        detections = []
        for index in nms(boxes, scores, classes, config['iou']):
            box = boxes[index].copy()
            box[[0, 2]] = np.clip((box[[0, 2]] - left) / ratio, 0, w)
            box[[1, 3]] = np.clip((box[[1, 3]] - top) / ratio, 0, h)
            if box[2] <= box[0] or box[3] <= box[1]:
                raise RuntimeError('Detector returned an empty defect box.')
            class_id = int(classes[index])
            detections.append(dict(class_id=class_id, label=('scratch', 'crack')[class_id],
                                   confidence=float(scores[index]), xyxy=list(map(float, box)), simulated=False))
        self.last_raw_detections = list(detections)
        threshold = config.get('scratch_nms_iou')
        return filter_scratch_duplicates(detections, threshold) if threshold is not None else detections


class OnnxShapeClassifier:
    def __init__(self, model_path, device='cpu'):
        self.path = Path(model_path)
        self.model = None
        self.config = None

    def classify(self, image):
        if not self.path.is_file():
            return dict(status='unavailable', reason='shape_model_missing', model=str(self.path))
        try:
            if self.model is None:
                metadata = json.loads(self.path.with_name('shape_preprocess.json').read_text())
                if metadata.get('format') != 'vdi_shape_mobilenet_v1' or metadata['classes'] != CLASS_NAMES:
                    raise ValueError('Wrong shape model format or classes.')
                self.config = metadata['preprocess']
                self.model = session_for(self.path)
                self._input_name = self.model.get_inputs()[0].name
                self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
            prepared = prepare_pil(Image.fromarray(image[:, :, ::-1]), self.config)
            array = np.asarray(prepared).astype(np.float32) / 255.
            array = (array - np.array(self.config['mean'], np.float32)) / np.array(self.config['std'], np.float32)
            tensor = np.ascontiguousarray(array.transpose(2, 0, 1)[None])
            logits = self.model.run(None, {self._input_name: tensor})[0][0]
            values = np.exp(logits - np.max(logits))
            values = values / values.sum()
            record = decide_shape(dict(zip(CLASS_NAMES, map(float, values))))
            record.update(model=str(self.path), device='cpu', model_sha256=self.sha256,
                          preprocess=self.config, backend='onnxruntime_cpu')
            return record
        except Exception as exc:
            return dict(status='uncertain', reason='shape_analysis_error', detail=str(exc), model=str(self.path))
