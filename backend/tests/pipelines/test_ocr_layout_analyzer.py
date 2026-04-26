from app.pipelines.identification import OcrTextLine
from app.pipelines.identification.ocr_layout_analyzer import analyze_ocr_layout


def test_ocr_layout_analyzer_extracts_release_title_and_label_roles() -> None:
    roles = analyze_ocr_layout(
        (
            OcrTextLine(text="THE", confidence=None, source="tesseract"),
            OcrTextLine(text="ESSENTIALS EP", confidence=None, source="tesseract"),
            OcrTextLine(text="FMROO?", confidence=None, source="tesseract"),
            OcrTextLine(text="P Fresh Milk", confidence=None, source="tesseract"),
            OcrTextLine(text="RECORDS |", confidence=None, source="tesseract"),
        )
    )

    assert ("release_title", "ESSENTIALS EP") in {(role.role, role.text) for role in roles}
    assert ("label", "Fresh Milk RECORDS") in {(role.role, role.text) for role in roles}
