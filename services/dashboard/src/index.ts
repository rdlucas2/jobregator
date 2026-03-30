import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { getDb, getListings, getListingById, type ListingsQuery } from "./db.js";
import { layout, listingTable, listingDetail } from "./templates.js";

const app = new Hono();

const DATABASE_URL = process.env.DATABASE_URL ?? "postgresql://jobregator:jobregator@localhost:5432/jobregator";
const PORT = Number(process.env.PORT ?? "3000");

const db = getDb(DATABASE_URL);

function parseQuery(c: { req: { query: (key: string) => string | undefined } }): ListingsQuery {
  const page = Number(c.req.query("page") ?? "1");
  const minScore = c.req.query("min_score") ? Number(c.req.query("min_score")) : undefined;
  const maxScore = c.req.query("max_score") ? Number(c.req.query("max_score")) : undefined;
  const search = c.req.query("search") || undefined;
  const source = c.req.query("source") || undefined;
  return { page, minScore, maxScore, search, source };
}

// Main page — full HTML
app.get("/", async (c) => {
  const query = parseQuery(c);
  const { listings, total } = await getListings(db, query);
  const totalPages = Math.ceil(total / 25);

  const filtersHtml = `
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
      <label>Source
        <input type="text" name="source" value="${query.source ?? ""}"
               hx-get="/listings" hx-target="#listing-results" hx-swap="innerHTML"
               hx-trigger="change" hx-include=".filters" />
      </label>
    </div>
  `;

  const content = `
    <h1>Jobregator Dashboard</h1>
    <p style="color: #aaa; margin-bottom: 1rem;">${total} listings</p>
    ${filtersHtml}
    <div id="listing-results">
      ${listingTable(listings, query.page ?? 1, totalPages)}
    </div>
  `;

  return c.html(layout("Jobregator", content));
});

// Listing fragments for htmx
app.get("/listings", async (c) => {
  const query = parseQuery(c);
  const { listings, total } = await getListings(db, query);
  const totalPages = Math.ceil(total / 25);
  return c.html(listingTable(listings, query.page ?? 1, totalPages));
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

console.log(`Dashboard starting on port ${PORT}`);
serve({ fetch: app.fetch, port: PORT });

export { app };
