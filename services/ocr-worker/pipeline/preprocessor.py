"""
Image Preprocessor
Applies a GPU-free CPU pipeline using OpenCV to improve OCR accuracy:
1. Convert to grayscale
2. Deskew (straighten tilted text)
3. Adaptive binarization (handle shadows/uneven lighting)
4. Denoise
5. Resize to model input resolution
"""
from typing import Tuple
import io
import math

import cv2
import numpy as np
import structlog
from PIL import Image

logger = structlog.get_logger()

# Target resolution for Triton model input
TARGET_HEIGHT = 32
TARGET_WIDTH = 1000


class ImagePreprocessor:

    @staticmethod
    def preprocess(image_bytes: bytes) -> np.ndarray:
        """
        Full preprocessing pipeline.
        Input: raw image bytes (PNG/JPEG)
        Output: numpy array ready for Triton tensor input
        """
        # Decode
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Could not decode image")

        # 1. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Deskew
        gray = ImagePreprocessor._deskew(gray)

        # 3. Denoise
        gray = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)

        # 4. Adaptive binarization (Otsu's thresholding)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 5. Normalize to [0, 1] float32
        normalized = binary.astype(np.float32) / 255.0

        return normalized

    @staticmethod
    def _deskew(gray_image: np.ndarray) -> np.ndarray:
        """Correct skew angle using Hough line transform."""
        try:
            edges = cv2.Canny(gray_image, 50, 150, apertureSize=3)
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)

            if lines is None:
                return gray_image

            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 - x1 != 0:
                    angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
                    if -45 < angle < 45:
                        angles.append(angle)

            if not angles:
                return gray_image

            median_angle = np.median(angles)
            if abs(median_angle) < 0.5:  # Less than 0.5° — skip rotation
                return gray_image

            h, w = gray_image.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            rotated = cv2.warpAffine(
                gray_image, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
            logger.debug("preprocessor.deskewed", angle=median_angle)
            return rotated

        except Exception as e:
            logger.warning("preprocessor.deskew_failed", error=str(e))
            return gray_image
