from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from media_delivery.infrai import InfraiClient, InfraiError
from media_delivery.service import CreatorDeliveryRequest, deliver_processed_asset


class DeliveryRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=80)
    creator_id: str = Field(min_length=1, max_length=80)
    creator_phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    asset_title: str = Field(min_length=1, max_length=120)
    processing_state: Literal["ingested", "processing", "ready", "rejected"]


app = FastAPI(title="Media SMS delivery observer")


@app.post("/creator-deliveries")
def create_creator_delivery(body: DeliveryRequestBody) -> dict[str, object]:
    try:
        request = CreatorDeliveryRequest(**body.model_dump())
        return asdict(deliver_processed_asset(InfraiClient(), request))
    except InfraiError as exc:
        caller_status = exc.status if 400 <= exc.status < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc

