from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeDependencyStatus:
    name: str
    available: bool
    detail: str


def get_runtime_dependency_statuses() -> tuple[RuntimeDependencyStatus, ...]:
    return (
        _check_tesseract(),
        _check_zbar(),
    )


def log_runtime_dependency_statuses() -> None:
    for status in get_runtime_dependency_statuses():
        if status.available:
            logger.info("Runtime dependency available name=%s detail=%s", status.name, status.detail)
            continue

        logger.warning("Runtime dependency unavailable name=%s detail=%s", status.name, status.detail)


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
