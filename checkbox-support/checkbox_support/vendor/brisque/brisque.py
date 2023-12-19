import collections
from itertools import chain
import pickle
import os
import math

import cv2
import numpy as np

try:
    from .svm import svmutil
except:
    from libsvm import svmutil

from .models import MODEL_PATH


class BRISQUE:
    def __init__(self):
        self.model = os.path.join(MODEL_PATH, "svm.txt")
        self.norm = os.path.join(MODEL_PATH, "normalize.pickle")

        # Load in model
        self.model = svmutil.svm_load_model(self.model)
        with open(self.norm, "rb") as f:
            self.scale_params = pickle.load(f)

    def preprocess_image(self, img):
        grey_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Resize image to a width of 640
        desired_width = int(640)
        height, width = grey_img.shape
        aspect_ratio = width / height
        desired_height = int(desired_width / aspect_ratio)
        resized_image = cv2.resize(
            grey_img,
            (desired_width, desired_height),
            interpolation=cv2.INTER_NEAREST,
        )

        float_img = np.float64(resized_image) / 255.0
        return float_img

    def score(self, img):
        proc_img = self.preprocess_image(img)
        # Don't calculate score if image is too homogeneous
        if np.std(proc_img) < 1e-2:
            return float("nan")
        brisque_features = self.calculate_brisque_features(
            proc_img, kernel_size=7, sigma=7 / 6
        )
        downscaled_image = cv2.resize(
            proc_img, None, fx=1 / 2, fy=1 / 2, interpolation=cv2.INTER_CUBIC
        )
        downscale_brisque_features = self.calculate_brisque_features(
            downscaled_image, kernel_size=7, sigma=7 / 6
        )
        brisque_features = np.concatenate(
            (brisque_features, downscale_brisque_features)
        )

        return self.calculate_image_quality_score(brisque_features)

    def normalize_kernel(self, kernel):
        return kernel / np.sum(kernel)

    def gaussian_kernel2d(self, n, sigma):
        Y, X = np.indices((n, n)) - int(n / 2)
        gaussian_kernel = (
            1
            / (2 * np.pi * sigma**2)
            * (np.exp(-(X**2 + Y**2) / (2 * sigma**2)))
        )
        return self.normalize_kernel(gaussian_kernel)

    def local_mean(self, image, kernel):
        return cv2.filter2D(
            image, -1, cv2.flip(kernel, -1), borderType=cv2.BORDER_CONSTANT
        )

    def local_deviation(self, image, local_mean, kernel):
        "Vectorized approximation of local deviation"
        sigma = image**2
        sigma = self.local_mean(sigma, kernel)
        return np.sqrt(np.abs(local_mean**2 - sigma))

    def calculate_mscn_coeff(self, image, kernel_size=6, sigma=7 / 6):
        C = 1 / 255
        kernel = self.gaussian_kernel2d(kernel_size, sigma=sigma)
        local_mean = self.local_mean(image, kernel)
        local_var = self.local_deviation(image, local_mean, kernel)

        return (image - local_mean) / (local_var + C)

    def generalized_gaussian_dist(self, x, alpha, sigma):
        beta = sigma * np.sqrt(math.gamma(1 / alpha) / math.gamma(3 / alpha))

        coefficient = alpha / (2 * beta() * math.gamma(1 / alpha))
        return coefficient * np.exp(-((np.abs(x) / beta) ** alpha))

    def calculate_pair_product_coeff(self, mscn_coeff):
        od = collections.OrderedDict()
        od["mscn"] = mscn_coeff
        od["horizontal"] = mscn_coeff[:, :-1] * mscn_coeff[:, 1:]
        od["vertical"] = mscn_coeff[:-1, :] * mscn_coeff[1:, :]
        od["main_diagonal"] = mscn_coeff[:-1, :-1] * mscn_coeff[1:, 1:]
        od["secondary_diagonal"] = mscn_coeff[1:, :-1] * mscn_coeff[:-1, 1:]
        return od

    def asymmetric_generalized_gaussian(self, x, nu, sigma_l, sigma_r):
        def beta(sigma):
            return sigma * np.sqrt(math.gamma(1 / nu) / math.gamma(3 / nu))

        def f_par(x, sigma):
            return coefficient * np.exp(-((x / beta(sigma)) ** nu))

        coefficient = nu / (
            (beta(sigma_l) + beta(sigma_r)) * math.gamma(1 / nu)
        )

        return np.where(x < 0, f_par(-x, sigma_l), f_par(x, sigma_r))

    def asymmetric_generalized_gaussian_fit(self, x):
        def estimate_phi(alpha):
            numerator = math.gamma(2 / alpha) ** 2
            denominator = math.gamma(1 / alpha) * math.gamma(3 / alpha)
            return numerator / denominator

        def estimate_r_hat(x):
            size = np.prod(x.shape)
            return (np.sum(np.abs(x)) / size) ** 2 / (np.sum(x**2) / size)

        def estimate_R_hat(r_hat, gamma):
            numerator = (gamma**3 + 1) * (gamma + 1)
            denominator = (gamma**2 + 1) ** 2
            return r_hat * numerator / denominator

        def mean_squares_sum(x, filter=lambda z: z == z):
            filtered_values = x[filter(x)]
            squares_sum = np.sum(filtered_values**2)
            return squares_sum / ((filtered_values.shape))

        def estimate_gamma(x):
            left_squares = mean_squares_sum(x, lambda z: z < 0)
            right_squares = mean_squares_sum(x, lambda z: z >= 0)

            return np.sqrt(left_squares) / np.sqrt(right_squares)

        def estimate_alpha(x):
            r_hat = estimate_r_hat(x)
            gamma = estimate_gamma(x)
            R_hat = estimate_R_hat(r_hat, gamma)

            # Alternative implementation with scipy.optimize.root
            # solution = optimize.root(lambda z: estimate_phi(z) -
            #                          R_hat, [0.2]).x[0]
            x_arr = np.arange(0.025, 10 + 0.001, 0.001)
            phy_arr = np.asarray([estimate_phi(z) for z in x_arr])
            pos = np.argmin(np.abs(phy_arr - R_hat))
            solution = x_arr[pos]

            return solution

        def estimate_sigma(x, alpha, filter=lambda z: z < 0):
            return np.sqrt(mean_squares_sum(x, filter))

        def estimate_mean(alpha, sigma_l, sigma_r):
            return (
                (sigma_r - sigma_l)
                * constant
                * (math.gamma(2 / alpha) / math.gamma(1 / alpha))
            )

        alpha = estimate_alpha(x)
        sigma_l = estimate_sigma(x, alpha, lambda z: z < 0)
        sigma_r = estimate_sigma(x, alpha, lambda z: z >= 0)

        constant = np.sqrt(math.gamma(1 / alpha) / math.gamma(3 / alpha))
        mean = estimate_mean(alpha, sigma_l, sigma_r)

        return alpha, mean, sigma_l, sigma_r

    def calculate_brisque_features(self, image, kernel_size=7, sigma=7 / 6):
        def calculate_features(coeff_name, coeff):
            (
                alpha,
                mean,
                sigma_l,
                sigma_r,
            ) = self.asymmetric_generalized_gaussian_fit(coeff)

            if coeff_name == "mscn":
                var = (sigma_l**2 + sigma_r**2) / 2
                return [alpha, var]

            return [alpha, mean, sigma_l**2, sigma_r**2]

        mscn_coeff = self.calculate_mscn_coeff(image, kernel_size, sigma)
        coeff = self.calculate_pair_product_coeff(mscn_coeff)

        features = [
            calculate_features(coeff_name=name, coeff=cf)
            for name, cf in coeff.items()
        ]
        flatten_features = list(chain.from_iterable(features))
        return np.array(flatten_features, dtype=object)

    def scale_features(self, features):
        min_ = np.array(self.scale_params["min_"], dtype=np.float64)
        max_ = np.array(self.scale_params["max_"], dtype=np.float64)
        features = np.array(features, dtype=np.float64)

        return (2.0 / (max_ - min_) * (features - min_)) - 1

    def calculate_image_quality_score(self, brisque_features):
        scaled_brisque_features = self.scale_features(brisque_features)

        x, idx = svmutil.gen_svm_nodearray(
            list(scaled_brisque_features),
            isKernel=(self.model.param.kernel_type == svmutil.PRECOMPUTED),
        )

        nr_classifier = 1
        prob_estimates = (svmutil.c_double * nr_classifier)()

        return svmutil.libsvm.svm_predict_probability(
            self.model, x, prob_estimates
        )
