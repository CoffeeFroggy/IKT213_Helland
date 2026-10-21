# Assignment 4

I used Harris corner detection to mark corners in the reference image.

For the image alignment, I used SIFT with FLANN matching and RANSAC
to calculate the homography.

The ratio test threshold is 0.7. I used max_features=10 as the minimum
number of good matches, following MIN_MATCH_COUNT in the OpenCV tutorial.

Run the code with `python assignment_4.py`.
OpenCV and NumPy must be installed, and both input images must be
in the same folder as the Python file.

The results are saved in the outputs folder:
- harris.png: the reference image with marked corners
- aligned.png: the image aligned with the reference
- matches.png: the matching points between the two images