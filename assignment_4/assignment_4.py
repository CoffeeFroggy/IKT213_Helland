from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"


# II part 1: Harris Corner Detection
def harris_corner_detection(reference_image):

    gray_image = cv2.cvtColor(
        reference_image,
        cv2.COLOR_BGR2GRAY
    )

    gray_image = np.float32(gray_image)

    corner_response = cv2.cornerHarris(
        gray_image,
        blockSize=2,
        ksize=3,
        k=0.04
    )

    corner_response = cv2.dilate(corner_response, None)

    marked_image = reference_image.copy()

    marked_image[
        corner_response > 0.01 * corner_response.max()
    ] = [0, 0, 255]

    OUTPUT_DIR.mkdir(exist_ok=True)

    if not cv2.imwrite(
        str(OUTPUT_DIR / "harris.png"),
        marked_image
    ):
        raise OSError("Could not save harris.png")

    return marked_image


def resize_for_matches(image, keypoints, target_height):

    scale = target_height / image.shape[0]
    target_width = round(image.shape[1] * scale)

    resized_image = cv2.resize(
        image,
        (target_width, target_height),
        interpolation=cv2.INTER_AREA
    )

    resized_keypoints = [
        cv2.KeyPoint(
            point.pt[0] * scale,
            point.pt[1] * scale,
            point.size * scale
        )
        for point in keypoints
    ]

    return resized_image, resized_keypoints


# II part 2: Feature-Based Image Alignment using SIFT and FLANN
def feature_based_image_alignment(
    image_to_align, reference_image, max_features, good_match_precent
):

    if not 0 < good_match_precent <= 1:
        raise ValueError("good_match_precent must be between 0 and 1.")

    gray_to_align = cv2.cvtColor(
        image_to_align,
        cv2.COLOR_BGR2GRAY
    )

    gray_reference = cv2.cvtColor(
        reference_image,
        cv2.COLOR_BGR2GRAY
    )

    # Interpret the assignment's 10 as MIN_MATCH_COUNT
    # from the linked SIFT tutorial.
    minimum_matches = max(4, max_features)

    sift = cv2.SIFT_create()

    keypoints_to_align, descriptors_to_align = sift.detectAndCompute(
        gray_to_align, None
    )

    keypoints_reference, descriptors_reference = sift.detectAndCompute(
        gray_reference, None
    )

    if descriptors_to_align is None or descriptors_reference is None:
        raise ValueError("Not enough features were found in the images.")

    if len(descriptors_reference) < 2:
        raise ValueError("At least two reference descriptors are needed.")

    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)

    matcher = cv2.FlannBasedMatcher(
        index_params,
        search_params
    )

    matches = matcher.knnMatch(
        descriptors_to_align,
        descriptors_reference,
        k=2
    )

    good_matches = []

    for pair in matches:
        if len(pair) == 2:
            best, second_best = pair

            if best.distance < good_match_precent * second_best.distance:
                good_matches.append(best)

    good_matches = sorted(
        good_matches,
        key=lambda x: x.distance,
        reverse=False
    )

    if len(good_matches) < minimum_matches:
        raise ValueError(
            f"Only {len(good_matches)} good matches were found; "
            f"at least {minimum_matches} are needed."
        )

    points_to_align = np.float32([
        keypoints_to_align[match.queryIdx].pt
        for match in good_matches
    ])

    points_reference = np.float32([
        keypoints_reference[match.trainIdx].pt
        for match in good_matches
    ])

    homography, inliers = cv2.findHomography(
        points_to_align,
        points_reference,
        cv2.RANSAC,
        5.0
    )

    if homography is None or inliers is None or int(inliers.sum()) < 4:
        raise ValueError("A reliable homography could not be calculated.")

    height, width = reference_image.shape[:2]

    aligned_image = cv2.warpPerspective(
        image_to_align,
        homography,
        (width, height)
    )

    # Resize only the display. Matching and alignment use original coordinates.
    display_height = min(
        1200, image_to_align.shape[0], reference_image.shape[0]
    )

    display_to_align, display_keypoints_to_align = resize_for_matches(
        image_to_align,
        keypoints_to_align,
        display_height
    )

    display_reference, display_keypoints_reference = resize_for_matches(
        reference_image,
        keypoints_reference,
        display_height
    )

    matches_image = cv2.drawMatches(
        display_to_align,
        display_keypoints_to_align,
        display_reference,
        display_keypoints_reference,
        good_matches,
        None,
        matchColor=(0, 255, 0),
        matchesMask=inliers.ravel().tolist(),
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
    )

    OUTPUT_DIR.mkdir(exist_ok=True)

    if not cv2.imwrite(
        str(OUTPUT_DIR / "aligned.png"),
        aligned_image
    ):
        raise OSError("Could not save aligned.png")

    if not cv2.imwrite(
        str(OUTPUT_DIR / "matches.png"),
        matches_image
    ):
        raise OSError("Could not save matches.png")

    print(f"Good SIFT matches: {len(good_matches)}")
    print(f"RANSAC inliers: {int(inliers.sum())}")

    return aligned_image, matches_image, homography


if __name__ == "__main__":

    reference_image = cv2.imread(
        str(BASE_DIR / "reference_img.png")
    )

    image_to_align = cv2.imread(
        str(BASE_DIR / "align_this.jpg")
    )

    if reference_image is None:
        raise FileNotFoundError("Could not load reference_img.png")

    if image_to_align is None:
        raise FileNotFoundError("Could not load align_this.jpg")

    harris_corner_detection(reference_image)

    feature_based_image_alignment(
        image_to_align,
        reference_image,
        max_features=10,
        good_match_precent=0.7
    )

    print("Method used: SIFT with FLANN")
    print("Saved harris.png, aligned.png and matches.png in outputs")