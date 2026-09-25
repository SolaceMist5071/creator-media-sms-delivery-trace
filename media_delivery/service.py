from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


ProcessingState = Literal["ingested", "processing", "ready", "rejected"]
DeliveryState = Literal["delivered", "pending", "failed", "not_sent"]


@dataclass(frozen=True)
class CreatorDeliveryRequest:
    asset_id: str
    creator_id: str
    creator_phone: str
    asset_title: str
    processing_state: ProcessingState


@dataclass(frozen=True)
class CreatorDeliveryResult:
    asset_id: str
    processing_state: ProcessingState
    delivery_state: DeliveryState
    message_id: str | None
    reason: str


def delivery_state(events_payload: Any) -> DeliveryState:
    if isinstance(events_payload, dict):
        events = events_payload.get("events", events_payload.get("items", []))
    else:
        events = events_payload
    normalized = " ".join(str(event).lower() for event in events or [])
    if "deliver" in normalized:
        return "delivered"
    if any(word in normalized for word in ("fail", "reject", "undeliver")):
        return "failed"
    return "pending"


def deliver_processed_asset(
    client: Any, request: CreatorDeliveryRequest
) -> CreatorDeliveryResult:
    if request.processing_state != "ready":
        return CreatorDeliveryResult(
            asset_id=request.asset_id,
            processing_state=request.processing_state,
            delivery_state="not_sent",
            message_id=None,
            reason="asset processing is not complete",
        )

    operation_id = f"creator-media:{request.asset_id}:{request.creator_id}"
    sent = client.send_creator_text(
        phone=request.creator_phone,
        text=f"{request.asset_title} is processed and ready to stream.",
        operation_id=operation_id,
    )
    data = sent.get("data") or {}
    message_id = str(data["message_id"])
    events = client.sms_events(message_id)
    state = delivery_state(events.get("data"))
    client.report_delivery_metric(
        name="media_sms.delivery",
        value=1.0 if state == "delivered" else 0.0,
        asset_id=request.asset_id,
        message_id=message_id,
        operation_id=f"{operation_id}:delivery",
    )
    return CreatorDeliveryResult(
        asset_id=request.asset_id,
        processing_state=request.processing_state,
        delivery_state=state,
        message_id=message_id,
        reason="delivery event and metric recorded",
    )
