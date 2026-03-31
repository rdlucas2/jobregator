import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { streamSSE } from "hono/streaming";
import { connect, AckPolicy, DeliverPolicy } from "nats";
import { getDb, getListings, getListingById, getSources, getScoreDistribution, getDailyCounts, getTopCompanies, type ListingsQuery, type SortColumn, type SortOrder } from "./db.js";
import { layout, listingTable, listingDetail, listingRow, chartsSection, type Listing, type SortState } from "./templates.js";

const app = new Hono();

const DATABASE_URL = process.env.DATABASE_URL ?? "postgresql://jobregator:jobregator@localhost:5432/jobregator";
const NATS_URL = process.env.NATS_URL ?? "nats://localhost:4222";
const PORT = Number(process.env.PORT ?? "3000");

const db = getDb(DATABASE_URL);

// SSE clients
const sseClients = new Set<(data: string) => void>();

// NATS subscription for live updates
async function startNatsSubscription() {
  try {
    const nc = await connect({ servers: NATS_URL });
    const js = nc.jetstream();
    const jsm = await nc.jetstreamManager();

    // Ensure stream exists
    try {
      await jsm.streams.info("JOBS");
    } catch {
      await jsm.streams.add({ name: "JOBS", subjects: ["jobs.>"] });
    }

    // Create or get durable consumer — deliver only new messages
    try {
      await jsm.consumers.add("JOBS", {
        durable_name: "dashboard",
        filter_subject: "jobs.enriched",
        ack_policy: AckPolicy.Explicit,
        deliver_policy: DeliverPolicy.New,
      });
    } catch {
      // Consumer already exists, that's fine
    }

    const consumer = await js.consumers.get("JOBS", "dashboard");

    (async () => {
      const messages = await consumer.consume();
      for await (const msg of messages) {
        try {
          const listing = JSON.parse(new TextDecoder().decode(msg.data));
          // Look up the full listing from Postgres (it should be there by now)
          const rows = await db.unsafe(
            `SELECT id, source, external_id, title, company, location, url, salary,
                    posted_at, fit_score, enriched_json
             FROM job_listings WHERE source = $1 AND external_id = $2`,
            [listing.source, listing.external_id],
          );

          if (rows.length > 0) {
            const row = listingRow(rows[0] as unknown as Listing);
            const wrappedRow = row.replace("<tr>", '<tr class="new-row">');
            for (const send of sseClients) {
              send(wrappedRow);
            }
          }
        } catch (e) {
          console.error("Error processing NATS message for SSE:", e);
        }
        msg.ack();
      }
    })();

    console.log("NATS subscription active for live dashboard updates");
  } catch (e) {
    console.error("Failed to connect to NATS (live updates disabled):", e);
  }
}

const validSortColumns = new Set<SortColumn>(["title", "company", "location", "fit_score", "salary", "source", "posted_at"]);
const validSortOrders = new Set<SortOrder>(["asc", "desc"]);

function parseQuery(c: { req: { query: (key: string) => string | undefined } }): ListingsQuery {
  const page = Number(c.req.query("page") ?? "1");
  const minScore = c.req.query("min_score") ? Number(c.req.query("min_score")) : undefined;
  const maxScore = c.req.query("max_score") ? Number(c.req.query("max_score")) : undefined;
  const minSalary = c.req.query("min_salary") ? Number(c.req.query("min_salary")) : undefined;
  const maxSalary = c.req.query("max_salary") ? Number(c.req.query("max_salary")) : undefined;
  const search = c.req.query("search") || undefined;
  const source = c.req.query("source") || undefined;
  const sortByRaw = c.req.query("sort_by") as SortColumn | undefined;
  const sortBy = sortByRaw && validSortColumns.has(sortByRaw) ? sortByRaw : undefined;
  const sortOrderRaw = c.req.query("sort_order") as SortOrder | undefined;
  const sortOrder = sortOrderRaw && validSortOrders.has(sortOrderRaw) ? sortOrderRaw : undefined;
  return { page, minScore, maxScore, minSalary, maxSalary, search, source, sortBy, sortOrder };
}

function getSortState(query: ListingsQuery): SortState {
  return { sortBy: query.sortBy ?? "fit_score", sortOrder: query.sortOrder ?? "desc" };
}

// SSE endpoint for live updates
app.get("/events", (c) => {
  return streamSSE(c, async (stream) => {
    const send = (data: string) => {
      stream.writeSSE({ event: "new-listing", data });
    };
    sseClients.add(send);

    // Keep alive
    const keepAlive = setInterval(() => {
      stream.writeSSE({ event: "ping", data: "" });
    }, 15000);

    try {
      // Block until client disconnects
      await new Promise<void>((resolve) => {
        stream.onAbort(() => {
          resolve();
        });
      });
    } finally {
      clearInterval(keepAlive);
      sseClients.delete(send);
    }
  });
});

// Main page — full HTML
app.get("/", async (c) => {
  const query = parseQuery(c);
  const sort = getSortState(query);
  const { listings, total } = await getListings(db, query);
  const totalPages = Math.ceil(total / 25);
  const [sources, scores, daily, topCompanies] = await Promise.all([
    getSources(db),
    getScoreDistribution(db),
    getDailyCounts(db),
    getTopCompanies(db),
  ]);

  const sourceOptions = sources
    .map((s) => `<option value="${s}"${query.source === s ? " selected" : ""}>${s}</option>`)
    .join("");

  const content = `
    <h1><span class="live-badge"></span>Jobregator Dashboard</h1>
    <p style="color: #aaa; margin-bottom: 1rem;">${total} listings</p>
    ${chartsSection(scores, daily, topCompanies)}
    <div class="filters">
      <label>Search
        <input type="text" name="search" value="${query.search ?? ""}"
               hx-get="/listings" hx-target="#listing-results" hx-swap="innerHTML"
               hx-trigger="keyup changed delay:300ms" hx-include=".filters" />
      </label>
      <label>Min Score
        <input type="number" name="min_score" min="0" max="1" step="0.1"
               value="${query.minScore ?? ""}"
               hx-get="/listings" hx-target="#listing-results" hx-swap="innerHTML"
               hx-trigger="change" hx-include=".filters" />
      </label>
      <label>Min Salary
        <input type="number" name="min_salary" min="0" step="10000"
               value="${query.minSalary ?? ""}"
               hx-get="/listings" hx-target="#listing-results" hx-swap="innerHTML"
               hx-trigger="change" hx-include=".filters" />
      </label>
      <label>Max Salary
        <input type="number" name="max_salary" min="0" step="10000"
               value="${query.maxSalary ?? ""}"
               hx-get="/listings" hx-target="#listing-results" hx-swap="innerHTML"
               hx-trigger="change" hx-include=".filters" />
      </label>
      <label>Source
        <select name="source"
                hx-get="/listings" hx-target="#listing-results" hx-swap="innerHTML"
                hx-trigger="change" hx-include=".filters">
          <option value="">All</option>
          ${sourceOptions}
        </select>
      </label>
      <input type="hidden" name="sort_by" value="${sort.sortBy}" />
      <input type="hidden" name="sort_order" value="${sort.sortOrder}" />
    </div>
    <div id="listing-results">
      ${listingTable(listings, query.page ?? 1, totalPages, sort)}
    </div>
  `;

  return c.html(layout("Jobregator", content));
});

// Listing fragments for htmx (redirect if accessed directly)
app.get("/listings", async (c) => {
  if (!c.req.header("hx-request")) {
    return c.redirect("/");
  }
  const query = parseQuery(c);
  const sort = getSortState(query);
  const { listings, total } = await getListings(db, query);
  const totalPages = Math.ceil(total / 25);
  return c.html(listingTable(listings, query.page ?? 1, totalPages, sort));
});

// Detail page
app.get("/listings/:id", async (c) => {
  const id = Number(c.req.param("id"));
  const listing = await getListingById(db, id);

  if (!listing) {
    return c.html(layout("Not Found", "<h1>Listing not found</h1><p><a href='/'>&larr; Back</a></p>"), 404);
  }

  return c.html(layout(`${listing.title} - Jobregator`, listingDetail(listing)));
});

// Start NATS subscription (non-blocking)
startNatsSubscription();

console.log(`Dashboard starting on port ${PORT}`);
serve({ fetch: app.fetch, port: PORT });

export { app };
