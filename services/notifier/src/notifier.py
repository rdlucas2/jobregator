import asyncio
import json
import logging
import os
import signal

import nats
import requests

from src.notify import should_notify, build_discord_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
FIT_SCORE_THRESHOLD = float(os.environ.get("FIT_SCORE_THRESHOLD", "0.7"))

STREAM_NAME = "JOBS"
SUBJECT_ENRICHED = "jobs.enriched"
CONSUMER_NAME = "notifier"


async def run():
    if not DISCORD_WEBHOOK_URL:
        log.error("DISCORD_WEBHOOK_URL must be set")
        return

    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()
    log.info("connected to NATS at %s", NATS_URL)

    await js.add_stream(name=STREAM_NAME, subjects=["jobs.>"])

    stop = asyncio.Event()

    async def message_handler(msg):
        try:
            listing = json.loads(msg.data)
            source = listing.get("source", "?")
            external_id = listing.get("external_id", "?")
            enrichment = listing.get("enrichment", {})
            fit_score = enrichment.get("fit_score", 0.0)

            if should_notify(fit_score, threshold=FIT_SCORE_THRESHOLD):
                payload = build_discord_payload(listing)
                resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
                if resp.ok:
                    log.info("notified %s/%s: %s (score: %.2f)",
                             source, external_id, listing.get("title", ""), fit_score)
                else:
                    log.warning("discord webhook failed %d: %s", resp.status_code, resp.text)
            else:
                log.debug("skipped %s/%s (score: %.2f < threshold: %.2f)",
                          source, external_id, fit_score, FIT_SCORE_THRESHOLD)

            await msg.ack()
        except Exception:
            log.exception("error processing message")
            await msg.nak()

    sub = await js.subscribe(
        SUBJECT_ENRICHED,
        durable=CONSUMER_NAME,
        stream=STREAM_NAME,
        cb=message_handler,
    )
    log.info("subscribed to %s (durable: %s, threshold: %.2f)",
             SUBJECT_ENRICHED, CONSUMER_NAME, FIT_SCORE_THRESHOLD)

    def handle_signal():
        log.info("shutting down...")
        stop.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await stop.wait()

    await sub.unsubscribe()
    await nc.close()
    log.info("shutdown complete")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
