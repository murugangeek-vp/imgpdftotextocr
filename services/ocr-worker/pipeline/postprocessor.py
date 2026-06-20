"""
OCR Post-Processor Pipeline
Applies spelling correction, LayoutLM structure normalization,
and linguistic cleanup.
"""
from typing import List
import json
import structlog

logger = structlog.get_logger()


class OCRPostProcessor:

    def __init__(self, languages: List[str]):
        self.languages = languages

    def process(self, raw_results: List[dict]) -> List[dict]:
        """
        Process Triton inference results:
        1. Parse structure & layout
        2. Run spell checks
        3. Convert to schema-compatible PageResult list
        """
        processed_pages = []
        for idx, page in enumerate(raw_results):
            text = page.get("text", "")
            corrected_text = self._correct_spelling(text)

            # Map blocks (mock LayoutLM structured formatting)
            blocks = page.get(
                "blocks",
                [
                    {
                        "type": "paragraph",
                        "text": corrected_text,
                        "confidence": page.get("confidence", 0.95),
                        "box": [0, 0, 1000, 1000],
                    }
                ],
            )

            layout_json = {
                "layout_type": "standard",
                "blocks": blocks,
                "detected_languages": self.languages,
            }

            processed_pages.append(
                {
                    "page_number": idx + 1,
                    "text": corrected_text,
                    "layout_json": json.dumps(layout_json),
                    "confidence": page.get("confidence", 0.95),
                    "language": self.languages[0] if self.languages else "en",
                }
            )

        return processed_pages

    def _correct_spelling(self, text: str) -> str:
        """
        Simple OCR correction dictionary.
        In production, we can run a fine-tuned Hugging Face transformer spell check model.
        """
        replacements = {
            "l1": "ll",
            "vv": "w",
            "rn": "m",  # common OCR confusion
            "0CR": "OCR",
        }
        for err, corr in replacements.items():
            text = text.replace(err, corr)
        return text
