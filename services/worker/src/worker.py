import asyncio
import json
import logging
import os
import signal

import nats
from nats.js.api import ConsumerConfig, DeliverPolicy

from src.db import get_connection, ensure_schema, insert_listing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
POSTGRES_DSN = os.environ.get(
    "POSTGRES_DSN",
    "postgresql://jobregator:jobregator@localhost:5432/jobregator",
)
STREAM_NAME = "JOBS"
SUBJECT_RAW = "jobs.raw"
CONSUMER_NAME = "worker"


async def run():
    db_conn = get_connection(POSTGRES_DSN)
    ensure_schema(db_conn)
    log.info("database schema ready")

    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()
    log.info("connected to NATS at %s", NATS_URL)

    sub = await js.subscribe(
        SUBJECT_RAW,
        durable=CONSUMER_NAME,
        stream=STREAM_NAME,
    )
    log.info("subscribed to %s (durable: %s)", SUBJECT_RAW, CONSUMER_NAME)

    stop = asyncio.Event()

    def handle_signal():
        log.info("shutting down...")
        stop.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    while not stop.is_set():
        try:
            msgs = await sub.fetch(batch=10, timeout=5)
            for msg in msgs:
                try:
                    listing = json.loads(msg.data)
                    listing["raw_json"] = json.dumps(listing)

                    inserted = insert_listing(db_conn, listing)
                    if inserted:
                        log.info("inserted listing %s/%s: %s",
                                 listing["source"], listing["external_id"], listing["title"])
                    else:
                        log.info("skipped duplicate %s/%s",
                                 listing["source"], listing["external_id"])

                    await msg.ack()
                except Exception:
                    log.exception("error processing message")
                    await msg.nak()
        except nats.errors.TimeoutError:
            continue
        except Exception:
            log.exception("error fetching messages")
            await asyncio.sleep(1)

    await sub.unsubscribe()
    await nc.close()
    db_conn.close()
    log.info("shutdown complete")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
