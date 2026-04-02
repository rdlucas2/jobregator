import asyncio
import json
import logging
import os
import signal

import nats
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.db import get_connection, ensure_schema, insert_listing, listing_exists, update_enrichment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

NATS_URL = os.environ.get("NATS_URL", "nats://localhost:4222")
POSTGRES_DSN = os.environ.get(
    "POSTGRES_DSN",
    "postgresql://jobregator:jobregator@localhost:5432/jobregator",
)
MCP_SERVER_CMD = os.environ.get("MCP_SERVER_CMD", "python")
MCP_SERVER_ARGS = os.environ.get("MCP_SERVER_ARGS", "-m src.server").split()
MCP_SERVER_WORKDIR = os.environ.get("MCP_SERVER_WORKDIR", "/mcp-server")
ENABLE_ENRICHMENT = os.environ.get("ENABLE_ENRICHMENT", "true").lower() == "true"

STREAM_NAME = "JOBS"
SUBJECT_RAW = "jobs.raw"
SUBJECT_ENRICHED = "jobs.enriched"
CONSUMER_NAME = "worker"


async def enrich_listing(mcp_session, listing: dict) -> dict | None:
    """Call MCP server tools to enrich a listing. Returns enrichment data or None on failure."""
    try:
        # Call analyze_job tool
        analyze_result = await mcp_session.call_tool(
            "analyze_job",
            arguments={
                "title": listing.get("title", ""),
                "company": listing.get("company", ""),
                "location": listing.get("location", ""),
                "description": listing.get("description", ""),
            },
        )
        analysis = json.loads(analyze_result.content[0].text)

        # Call score_job_fit tool
        score_result = await mcp_session.call_tool(
            "score_job_fit",
            arguments={
                "title": listing.get("title", ""),
                "company": listing.get("company", ""),
                "description": listing.get("description", ""),
            },
        )
        scoring = json.loads(score_result.content[0].text)

        return {
            "analysis": analysis,
            "scoring": scoring,
            "fit_score": scoring.get("score", 0.0),
        }
    except Exception:
        log.exception("error enriching listing %s/%s", listing.get("source"), listing.get("external_id"))
        return None


async def process_message(msg, db_conn, js, mcp_session):
    """Process a single NATS message."""
    try:
        listing = json.loads(msg.data)
        source = listing["source"]
        external_id = listing["external_id"]
        filter_reason = listing.get("filter_reason") or None

        # Insert raw listing (dedup at DB level)
        listing["raw_json"] = json.dumps(listing)
        listing["filter_reason"] = filter_reason
        inserted = insert_listing(db_conn, listing)

        if not inserted:
            log.info("skipped duplicate %s/%s", source, external_id)
            await msg.ack()
            return

        if filter_reason:
            log.info("inserted filtered listing %s/%s: %s (reason: %s)",
                     source, external_id, listing.get("title", ""), filter_reason)
            await msg.ack()
            return

        log.info("inserted listing %s/%s: %s", source, external_id, listing.get("title", ""))

        # Enrich via MCP if enabled (skip for filtered listings)
        if ENABLE_ENRICHMENT and mcp_session is not None:
            enrichment = await enrich_listing(mcp_session, listing)
            if enrichment:
                update_enrichment(
                    db_conn, source, external_id,
                    enriched_json={**enrichment["analysis"], **enrichment["scoring"]},
                    fit_score=enrichment["fit_score"],
                )
                log.info("enriched %s/%s — score: %.2f", source, external_id, enrichment["fit_score"])

                # Publish enriched listing to jobs.enriched
                enriched_msg = {**listing, "enrichment": enrichment}
                enriched_msg.pop("raw_json", None)
                await js.publish(SUBJECT_ENRICHED, json.dumps(enriched_msg).encode())
            else:
                log.warning("enrichment failed for %s/%s, stored raw only", source, external_id)

        await msg.ack()
    except Exception:
        log.exception("error processing message")
        await msg.nak()


async def run():
    db_conn = get_connection(POSTGRES_DSN)
    ensure_schema(db_conn)
    log.info("database schema ready")

    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()
    log.info("connected to NATS at %s", NATS_URL)

    await js.add_stream(name=STREAM_NAME, subjects=["jobs.>"])
    log.info("ensured NATS stream %s", STREAM_NAME)

    stop = asyncio.Event()

    def handle_signal():
        log.info("shutting down...")
        stop.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    if ENABLE_ENRICHMENT:
        log.info("enrichment enabled, connecting to MCP server...")
        server_params = StdioServerParameters(
            command=MCP_SERVER_CMD,
            args=MCP_SERVER_ARGS,
            cwd=MCP_SERVER_WORKDIR,
            env={
                **os.environ,
            },
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                log.info("MCP server connected, available tools: %s",
                         [t.name for t in tools.tools])

                async def handler(msg):
                    await process_message(msg, db_conn, js, session)

                sub = await js.subscribe(
                    SUBJECT_RAW,
                    durable=CONSUMER_NAME,
                    stream=STREAM_NAME,
                    cb=handler,
                )
                log.info("subscribed to %s (durable: %s, enrichment: on)", SUBJECT_RAW, CONSUMER_NAME)

                await stop.wait()
                await sub.unsubscribe()
    else:
        log.info("enrichment disabled, running in passthrough mode")

        async def handler(msg):
            await process_message(msg, db_conn, js, None)

        sub = await js.subscribe(
            SUBJECT_RAW,
            durable=CONSUMER_NAME,
            stream=STREAM_NAME,
            cb=handler,
        )
        log.info("subscribed to %s (durable: %s, enrichment: off)", SUBJECT_RAW, CONSUMER_NAME)

        await stop.wait()
        await sub.unsubscribe()

    await nc.close()
    db_conn.close()
    log.info("shutdown complete")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
