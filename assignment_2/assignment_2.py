import cv2
import numpy as np
# II part 1

image = cv2.imread("iris-1.png")

def padding(image, border_width):
    return cv2.copyMakeBorder(
        image,
        border_width, border_width, border_width, border_width,
        cv2.BORDER_REFLECT
    )


padded_image = padding(image, 100)
cv2.imwrite("padding.png", padded_image)

# II part 2

def crop(image, x_0, x_1, y_0, y_1):
    return image[y_0:y_1, x_0:x_1]


height, width = image.shape[:2]
cropped_image = crop(image, 200, width - 130, 200, height - 130)
cv2.imwrite("crop.png", cropped_image)

# II part 3

def resize(image, width, height):
    return cv2.resize(image, (width, height))


resized_image = resize(image, 200, 200)
cv2.imwrite("resize.png", resized_image)

#II part 4

def copy(image, emptyPictureArray):
    height, width, channels = image.shape

    for y in range(height):
        for x in range(width):
            for c in range(channels):
                emptyPictureArray[y, x, c] = image[y, x, c]

    return emptyPictureArray


height, width, channels = image.shape
emptyPictureArray = np.zeros((height, width, 3), dtype=np.uint8)

copied_image = copy(image, emptyPictureArray)
cv2.imwrite("copy.png", copied_image)

# II part 5

def grayscale(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


grayscale_image = grayscale(image)
cv2.imwrite("grayscale.png", grayscale_image)

# II part 6

def hsv(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2HSV)


hsv_image = hsv(image)
cv2.imwrite("hsv.png", hsv_image)

# II part 7

def hue_shifted(image, emptyPictureArray, hue):
    height, width, channels = image.shape

    for y in range(height):
        for x in range(width):
            for c in range(channels):
                value = int(image[y, x, c]) + hue
                emptyPictureArray[y, x, c] = np.clip(value, 0, 255)

    return emptyPictureArray


height, width, channels = image.shape
emptyPictureArray = np.zeros((height, width, 3), dtype=np.uint8)

hue_shifted_image = hue_shifted(image, emptyPictureArray, 50)
cv2.imwrite("hue_shifted.png", hue_shifted_image)

# II part 8

def smoothing(image):
    return cv2.GaussianBlur(
        image, (15, 15), 0, borderType=cv2.BORDER_DEFAULT
    )


smoothed_image = smoothing(image)
cv2.imwrite("smoothing.png", smoothed_image)

# II part 9

def rotation(image, rotation_angle):
    if rotation_angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    elif rotation_angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)


rotated_image = rotation(image, 180)
cv2.imwrite("rotation.png", rotated_image)
