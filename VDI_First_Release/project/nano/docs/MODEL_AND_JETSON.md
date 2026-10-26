# Nano runtime

Run `bash START_NANO.sh` on the Nano desktop. See the root README.

This build uses ONNX Runtime CPU inference, not the PC PyTorch packages. Both models use ONNX opset 12 / IR 7 for compatibility with ONNX Runtime 1.10.0 on Python 3.6 ARM64. No substitute model is downloaded.

Sources: https://onnxruntime.ai/docs/install/ and https://docs.ultralytics.com/integrations/onnx/ . NVIDIA Jetson Nano supports legacy JetPack 4; model conversion avoids installing a mismatched modern PyTorch wheel.
