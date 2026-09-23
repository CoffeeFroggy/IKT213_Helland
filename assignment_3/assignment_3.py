from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent


# II part 1
def sobel_edge_detection(image):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blurred_image = cv2.GaussianBlur(
        gray_image,
        ksize=(3, 3),
        sigmaX=0
    )

    sobel_edges = cv2.Sobel(
        blurred_image,
        ddepth=cv2.CV_64F,
        dx=1,
        dy=1,
        ksize=1
    )

    sobel_edges = cv2.convertScaleAbs(sobel_edges)

    output_path = BASE_DIR / "sobel_edges.png"

    if not cv2.imwrite(str(output_path), sobel_edges):
        raise IOError(f"Could not save the image: {output_path}")

    return sobel_edges


# II part 2
def canny_edge_detection(image, threshold_1, threshold_2):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blurred_image = cv2.GaussianBlur(
        gray_image,
        ksize=(3, 3),
        sigmaX=0
    )

    canny_edges = cv2.Canny(
        blurred_image,
        threshold1=threshold_1,
        threshold2=threshold_2
    )

    output_path = BASE_DIR / "canny_edges.png"

    if not cv2.imwrite(str(output_path), canny_edges):
        raise IOError(f"Could not save the image: {output_path}")

    return canny_edges


# II part 3
def template_match(image, template):
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    template_height, template_width = gray_template.shape

    matching_result = cv2.matchTemplate(
        gray_image,
        gray_template,
        cv2.TM_CCOEFF_NORMED
    )

    threshold = 0.9
    matched_locations = np.where(matching_result >= threshold)

    result_image = image.copy()

    for point in zip(*matched_locations[::-1]):
        top_left = point

        bottom_right = (
            point[0] + template_width,
            point[1] + template_height
        )

        cv2.rectangle(
            result_image,
            top_left,
            bottom_right,
            color=(0, 0, 255),
            thickness=2
        )

    output_path = BASE_DIR / "template_matches.png"

    if not cv2.imwrite(str(output_path), result_image):
        raise IOError(f"Could not save the image: {output_path}")

    return result_image


# II part 4
def resize(image, scale_factor: int, up_or_down: str):
    if not isinstance(scale_factor, int) or scale_factor != 2:
        raise ValueError("scale_factor must be the integer 2.")

    direction = up_or_down.strip().lower()

    height, width = image.shape[:2]

    if direction == "up":
        resized_image = cv2.pyrUp(
            image,
            dstsize=(
                width * scale_factor,
                height * scale_factor
            )
        )

        output_path = BASE_DIR / "resized_up.png"

    elif direction == "down":
        resized_image = cv2.pyrDown(
            image,
            dstsize=(
                width // scale_factor,
                height // scale_factor
            )
        )

        output_path = BASE_DIR / "resized_down.png"

    else:
        raise ValueError(
            'up_or_down must be either "up" or "down".'
        )

    if not cv2.imwrite(str(output_path), resized_image):
        raise IOError(f"Could not save the image: {output_path}")

    return resized_image


def main():
    image_path = BASE_DIR / "lambo.png"
    shapes_path = BASE_DIR / "shapes-1.png"
    template_path = BASE_DIR / "shapes_template.jpg"

    lambo_image = cv2.imread(str(image_path))
    shapes_image = cv2.imread(str(shapes_path))
    shapes_template = cv2.imread(str(template_path))

    if lambo_image is None:
        raise FileNotFoundError(
            f"Could not load {image_path}. "
            "Make sure lambo.png is in the assignment_3 folder."
        )

    if shapes_image is None:
        raise FileNotFoundError(
            f"Could not load {shapes_path}. "
            "Make sure shapes-1.png is in the assignment_3 folder."
        )

    if shapes_template is None:
        raise FileNotFoundError(
            f"Could not load {template_path}. "
            "Make sure shapes_template.jpg is in the assignment_3 folder."
        )

    sobel_edge_detection(lambo_image)

    canny_edge_detection(
        lambo_image,
        threshold_1=50,
        threshold_2=50
    )

    template_match(
        shapes_image,
        shapes_template
    )

    resize(
        lambo_image,
        scale_factor=2,
        up_or_down="up"
    )

    resize(
        lambo_image,
        scale_factor=2,
        up_or_down="down"
    )

    print("All operations completed successfully.")
    print(f"Results were saved in: {BASE_DIR}")


if __name__ == "__main__":
    main()