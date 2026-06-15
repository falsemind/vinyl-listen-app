from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.collection import CollectionSourceOfTruth


class DiscogsIntegrationStatusResponse(BaseModel):
    provider: Literal["DISCOGS"] = "DISCOGS"
    access_token_saved: bool
    external_user_id: str | None = None
    external_username: str | None = None
    source_of_truth: CollectionSourceOfTruth
    backend_identify_enabled: bool


class DiscogsTokenRequest(BaseModel):
    access_token: str = Field(min_length=1, max_length=4096)
