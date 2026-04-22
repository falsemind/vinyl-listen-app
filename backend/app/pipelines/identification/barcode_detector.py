from __future__ import annotations

import logging
from io import BytesIO

from PIL import Image

from app.pipelines.identification.models import PreparedImage

logger = logging.getLogger(__name__)

try:
    from pyzbar.pyzbar import decode as decode_barcodes
except (ImportError, OSError) as error:
    decode_barcodes = None
    IMPORT_ERROR = error
else:
    IMPORT_ERROR = None


class BarcodeDetector:
    def detect(self, prepared_image: PreparedImage) -> tuple[str, ...]:
        if decode_barcodes is None:
            logger.debug("Barcode detection unavailable because pyzbar/zbar is not loadable: %s", IMPORT_ERROR)
            return ()

        detected_barcodes: list[str] = []
        seen: set[str] = set()
        for variant in prepared_image.barcode_variants():
            with Image.open(BytesIO(variant.data)) as image:
                try:
                    symbols = decode_barcodes(image)
                except OSError as error:
                    logger.info("Barcode detection unavailable: %s", error)
                    return ()

            for symbol in symbols:
                value = _decode_barcode_payload(symbol.data)
                if not value or value in seen:
                    continue
                seen.add(value)
                detected_barcodes.append(value)

        return tuple(detected_barcodes)


def _decode_barcode_payload(payload: bytes) -> str | None:
    decoded_value = payload.decode("utf-8", errors="ignore")
    digits_only = "".join(character for character in decoded_value if character.isdigit())
    if 8 <= len(digits_only) <= 14:
        return digits_only

    return None
