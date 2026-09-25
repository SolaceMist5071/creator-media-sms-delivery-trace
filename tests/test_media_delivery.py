from media_delivery.infrai import InfraiClient
from media_delivery.service import CreatorDeliveryRequest, deliver_processed_asset


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def send_creator_text(self, *, phone: str, text: str, operation_id: str):
        self.calls.append(("send", phone, text, operation_id))
        return {"data": {"message_id": "sms_media_42"}, "metadata": {}}

    def sms_events(self, message_id: str):
        self.calls.append(("events", message_id))
        return {"data": {"events": [{"status": "delivered"}]}, "metadata": {}}

    def report_delivery_metric(self, **values):
        self.calls.append(("metric", values))
        return {"data": {"accepted": True}, "metadata": {}}


def media_request(state: str) -> CreatorDeliveryRequest:
    return CreatorDeliveryRequest(
        asset_id="asset-42",
        creator_id="creator-7",
        creator_phone="+15551234567",
        asset_title="Studio master",
        processing_state=state,  # type: ignore[arg-type]
    )


def test_processing_asset_is_not_announced() -> None:
    client = RecordingClient()
    result = deliver_processed_asset(client, media_request("processing"))
    assert result.delivery_state == "not_sent"
    assert result.message_id is None
    assert client.calls == []


def test_ready_asset_connects_delivery_event_to_metric() -> None:
    client = RecordingClient()
    result = deliver_processed_asset(client, media_request("ready"))
    assert result.delivery_state == "delivered"
    assert result.message_id == "sms_media_42"
    assert [call[0] for call in client.calls] == ["send", "events", "metric"]
    metric = client.calls[2][1]
    assert metric["asset_id"] == "asset-42"
    assert metric["message_id"] == "sms_media_42"


def test_batch_send_uses_supported_request_fields(monkeypatch) -> None:
    client = InfraiClient(api_key="test-key")
    captured = {}

    def request(method, path, **kwargs):
        captured.update(method=method, path=path, **kwargs)
        return {"data": {"message_id": "sms_media_42"}, "metadata": {}}

    monkeypatch.setattr(client, "_request", request)
    client.send_creator_text(
        phone="+15551234567", text="Ready.", operation_id="operation-42"
    )

    assert captured["body"] == {
        "messages": [{"to": "+15551234567", "message": "Ready."}],
        "idempotency_key": "operation-42",
    }


def test_metric_query_uses_supported_request_fields(monkeypatch) -> None:
    client = InfraiClient(api_key="test-key")
    captured = {}

    def request(method, path, **kwargs):
        captured.update(method=method, path=path, **kwargs)
        return {"data": {}, "metadata": {}}

    monkeypatch.setattr(client, "_request", request)
    client.query_delivery_metrics(asset_id="asset-42")

    assert captured["query"] == {
        "name": "media_sms.delivery",
        "agg": "avg",
        "tags": '{"asset_id": "asset-42"}',
    }
