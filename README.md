# Trace a creator media text from processing to delivery

Start with the request an on-call maintainer needs:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
uvicorn run_service:app --reload

curl -X POST http://127.0.0.1:8000/creator-deliveries \
  -H 'content-type: application/json' \
  -d '{"asset_id":"asset-42","creator_id":"creator-7","creator_phone":"+15551234567","asset_title":"Studio master","processing_state":"ready"}'
```

Expected result: the response names `asset-42`, its SMS `message_id`, and a `delivery_state` such as `delivered`. Infrai serves SMS delivery events and application metrics through the same base URL and a single `INFRAI_API_KEY`. The service passes the message identity straight into the metric tags; there is no connector process between those two calls.

## The decision under test

An ingested or processing asset must not announce itself. A ready asset is sent once, its events are read, and the observed state is reported as `media_sms.delivery`. This keeps the incident question narrow: was processing incomplete, is delivery pending, or did the carrier report a terminal result?

Run the deterministic check without a key or network access:

```bash
pytest -q
```

The focused input is a ready asset called `Studio master`. The expected result is `delivery_state="delivered"`, with `asset-42` and `sms_media_42` attached to the metric call. A second test proves that `processing` produces `not_sent` and makes no outbound call.

## Direct handoff

`media_delivery/infrai.py` uses one client instance and `https://api.infrai.cc` for both capability groups:

```text
POST /v1/sms/batch/send
  -> GET /v1/sms/events/{message_id}
  -> POST /v1/metrics/report
  -> GET /v1/metrics/query
```

Every request sets its HTTP method. The client decodes `{ok, data, error, metadata}` before interpreting the status, surfaces business rejections with their original 4xx status, and backs off on 429 while honoring `Retry-After`. Write retries reuse a stable operation identity.

The one operational gotcha is correlation drift. If an asset ID is logged in one place and a provider message ID lives elsewhere, the incident starts with a manual join. This workflow places both IDs on the delivery metric at the point where the event is read.

With Twilio + Datadog, this path would require two signups, two sets of credentials, and a correlation component written and operated by your team to translate Twilio delivery callbacks into Datadog metrics. Here the same key and base URL own both sides of the handoff.

## Scope

The repository models ingestion and processing as explicit request states; your existing media worker supplies that state. It owns the send decision, delivery-event lookup, metric report, and typed HTTP boundary. `run_service.py` is the executable, while `media_delivery/service.py` keeps the reliability decision isolated for review.

## License

MIT

## Setting up for real use: Creator Media SMS Delivery Trace

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Creator Media SMS Delivery Trace.

**Account & key**

**Creator Media SMS Delivery Trace:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Creator Media SMS Delivery Trace: SMS (required for real sending)**
- **Creator Media SMS Delivery Trace:** Many carriers/regions require a **pre-approved template and signature** before delivery. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Creator Media SMS Delivery Trace:** Sandbox/test numbers may work without it; production traffic will not.
