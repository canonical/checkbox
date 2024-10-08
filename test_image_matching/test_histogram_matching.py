import cv2
import numpy as np
from matplotlib import pyplot as plt
from skimage import exposure


def calculate_cdf(histogram):
    # Calculate the cumulative distribution function (CDF)
    cdf = histogram.cumsum()
    cdf_normalized = cdf * (255 / cdf[-1])  # Normalize to [0, 255]
    return cdf_normalized


def create_histogram_lut(input_cdf, reference_cdf):
    # Create LUT based on the CDF of both input and reference
    lut = np.zeros(256)
    for i in range(256):
        diff = np.abs(reference_cdf - input_cdf[i])
        lut[i] = np.argmin(diff)  # Find the closest value in the reference CDF
    return lut


def histogram_matching(input_gray, reference_gray):

    # Calculate histograms
    input_hist = cv2.calcHist(
        [input_gray], [0], None, [256], [0, 256]
    ).flatten()
    reference_hist = cv2.calcHist(
        [reference_gray], [0], None, [256], [0, 256]
    ).flatten()

    # Calculate the CDFs
    input_cdf = calculate_cdf(input_hist)
    reference_cdf = calculate_cdf(reference_hist)

    # Create the LUT for histogram matching
    lut = create_histogram_lut(input_cdf, reference_cdf)

    # Apply the LUT to the input image
    matched_image = cv2.LUT(input_gray, lut.astype(np.uint8))

    return matched_image


def skimage_histogram_matching(input_gray, reference_gray):

    # Convert to grayscale if needed (for simplicity)

    # Apply histogram matching
    matched_image = exposure.match_histograms(input_gray, reference_gray)

    return matched_image


# Example usage
input_image = cv2.imread(
    "/home/fernando/Canonical/image_matching/desktop_37_calc_cropped.png"
)
reference_image = cv2.imread(
    "/home/fernando/Canonical/image_matching/calculator.png"
)
# Perform histogram matching

input_gray = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
reference_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)
matched_image = skimage_histogram_matching(input_gray, reference_gray)

# Display the result
fig, ax = plt.subplots(1, 3, figsize=(20, 5))
ax[0].imshow(reference_gray, cmap="gray")
ax[0].set_title("Reference Image")
ax[1].imshow(input_gray, cmap="gray")
ax[1].set_title("Input Image")
ax[2].imshow(matched_image, cmap="gray")
ax[2].set_title("Matched Image")
plt.show()
