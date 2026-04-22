from pydantic import BaseModel


class IdentifyCandidateResponse(BaseModel):
    discogs_release_id: int
    release_id: str | None
    artist: str
    title: str
    year: int | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    cover_image_url: str | None
    match_source: str
    matched_on: list[str]
    confidence: float


class IdentifyResponse(BaseModel):
    candidates: list[IdentifyCandidateResponse]
