import cv2
import os


def print_image_information(image):
    height, width, channels = image.shape

    print("===== PART IV: IMAGE INFORMATION =====")
    print("Height:", height)
    print("Width:", width)
    print("Channels:", channels)
    print("Size:", image.size)
    print("Data type:", image.dtype)
    print()


def save_camera_information():
    camera = None
    camera_index_used = None

    # Try the camera devices available on the Ubuntu system
    for camera_index in [0, 1]:
        test_camera = cv2.VideoCapture(camera_index)

        if test_camera.isOpened():
            success, frame = test_camera.read()

            if success:
                camera = test_camera
                camera_index_used = camera_index
                break

        test_camera.release()

    if camera is None:
        print("===== PART V: CAMERA INFORMATION =====")
        print("Could not open camera")
        return

    fps = camera.get(cv2.CAP_PROP_FPS)
    height = camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
    width = camera.get(cv2.CAP_PROP_FRAME_WIDTH)

    print("===== PART V: CAMERA INFORMATION =====")
    print("Camera index used:", camera_index_used)
    print("FPS:", fps)
    print("Height:", height)
    print("Width:", width)

    file_path = os.path.join(
        os.path.dirname(__file__),
        "camera_outputs.txt"
    )

    with open(file_path, "w") as file:
        file.write(f"fps: {fps}\n")
        file.write(f"height: {height}\n")
        file.write(f"width: {width}\n")

    camera.release()

    print("Camera information saved to camera_outputs.txt")


def main():
    image = cv2.imread("../iris-1.jpg")

    print_image_information(image)
    save_camera_information()


if __name__ == "__main__":
    main()