import logging
import shutil
from dataclasses import dataclass
from importlib.util import find_spec

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeDependencyStatus:
    name: str
    available: bool
    detail: str
    warn_when_unavailable: bool = True


def get_runtime_dependency_statuses() -> tuple[RuntimeDependencyStatus, ...]:
    return (
        _check_tesseract(),
        _check_zbar(),
        _check_easyocr(),
        _check_opencv(),
    )


def log_runtime_dependency_statuses() -> None:
    for status in get_runtime_dependency_statuses():
        if status.available:
            logger.info("Runtime dependency available name=%s detail=%s", status.name, status.detail)
            continue

        if status.warn_when_unavailable:
            logger.warning("Runtime dependency unavailable name=%s detail=%s", status.name, status.detail)
            continue

        logger.info("Runtime dependency unavailable name=%s detail=%s", status.name, status.detail)


def _check_tesseract() -> RuntimeDependencyStatus:
    tesseract_path = shutil.which("tesseract")
    if tesseract_path is None:
        return RuntimeDependencyStatus(
            name="tesseract",
            available=False,
            detail="The tesseract binary is not on PATH.",
        )

    return RuntimeDependencyStatus(
        name="tesseract",
        available=True,
        detail=f"binary={tesseract_path}",
    )


def _check_zbar() -> RuntimeDependencyStatus:
    try:
        from pyzbar.pyzbar import decode as decode_barcodes
    except (ImportError, OSError) as error:
        return RuntimeDependencyStatus(
            name="zbar",
            available=False,
            detail=str(error),
        )

    if decode_barcodes is None:
        return RuntimeDependencyStatus(
            name="zbar",
            available=False,
            detail="pyzbar loaded without a decode implementation.",
        )

    return RuntimeDependencyStatus(
        name="zbar",
        available=True,
        detail="pyzbar decode loaded successfully.",
    )


def _check_easyocr() -> RuntimeDependencyStatus:
    if find_spec("easyocr") is None:
        return RuntimeDependencyStatus(
            name="easyocr",
            available=False,
            detail="Optional EasyOCR fallback is not installed.",
            warn_when_unavailable=settings.identify_easyocr_enabled,
        )

    return RuntimeDependencyStatus(
        name="easyocr",
        available=True,
        detail=f"module installed; enabled={settings.identify_easyocr_enabled}",
    )


def _check_opencv() -> RuntimeDependencyStatus:
    if find_spec("cv2") is None:
        return RuntimeDependencyStatus(
            name="opencv",
            available=False,
            detail="Optional OpenCV geometry preprocessing is not installed.",
            warn_when_unavailable=settings.identify_geometry_preprocess_enabled,
        )

    return RuntimeDependencyStatus(
        name="opencv",
        available=True,
        detail=f"module installed; enabled={settings.identify_geometry_preprocess_enabled}",
    )
