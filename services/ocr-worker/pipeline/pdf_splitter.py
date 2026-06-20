"""
PDF Splitter — splits a PDF into individual page images using PyMuPDF.
Each page is rendered at 300 DPI for optimal OCR accuracy.
"""
from typing import List
import io

import fitz  # PyMuPDF
import structlog

logger = structlog.get_logger()

# 300 DPI zoom factor (72 DPI base → 300/72 ≈ 4.17x)
DPI_ZOOM = fitz.Matrix(300 / 72, 300 / 72)


class PDFSplitter:

    @staticmethod
    def split(pdf_bytes: bytes) -> List[bytes]:
        """
        Split a PDF into individual page images (PNG bytes).
        Returns a list of PNG byte strings, one per page.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_images = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render at 300 DPI
            pix = page.get_pixmap(matrix=DPI_ZOOM, colorspace=fitz.csRGB)
            img_bytes = pix.tobytes("png")
            page_images.append(img_bytes)
            logger.debug("pdf_splitter.page_rendered", page=page_num + 1)

        doc.close()
        logger.info("pdf_splitter.done", total_pages=len(page_images))
        return page_images
