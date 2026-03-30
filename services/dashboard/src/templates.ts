import { html, raw } from "hono/html";

export interface Listing {
  id: number;
  source: string;
  external_id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  salary: string;
  posted_at: string;
  fit_score: number | null;
  enriched_json: Record<string, unknown> | null;
}

function scoreColor(score: number | null): string {
  if (score === null) return "#999";
  if (score >= 0.8) return "#2ecc71";
  if (score >= 0.6) return "#f1c40f";
  return "#e74c3c";
}

function scoreDisplay(score: number | null): string {
  if (score === null) return "—";
  return score.toFixed(2);
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function layout(title: string, content: string): string {
  return html`<!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${title}</title>
        <script src="https://unpkg.com/htmx.org@2.0.4"></script>
        <style>
          * { box-sizing: border-box; margin: 0; padding: 0; }
          body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f1117; color: #e1e1e6; line-height: 1.6; }
          .container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
          h1 { font-size: 1.5rem; margin-bottom: 1rem; color: #fff; }
          h2 { font-size: 1.2rem; margin-bottom: 0.5rem; color: #fff; }
          a { color: #58a6ff; text-decoration: none; }
          a:hover { text-decoration: underline; }

          .filters { display: flex; gap: 0.75rem; margin-bottom: 1rem; flex-wrap: wrap; align-items: end; }
          .filters label { font-size: 0.85rem; color: #aaa; display: flex; flex-direction: column; gap: 0.25rem; }
          .filters input, .filters select { background: #1c1f26; border: 1px solid #333; color: #e1e1e6; padding: 0.4rem 0.6rem; border-radius: 4px; font-size: 0.9rem; }
          .filters button { background: #238636; color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }
          .filters button:hover { background: #2ea043; }

          table { width: 100%; border-collapse: collapse; }
          th, td { text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid #1c1f26; }
          th { background: #161b22; color: #aaa; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; position: sticky; top: 0; }
          tr:hover { background: #161b22; }

          .score { font-weight: 600; font-size: 0.95rem; }
          .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 3px; font-size: 0.75rem; background: #1c1f26; }

          .detail { background: #161b22; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; }
          .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem; }
          .detail-field { }
          .detail-field dt { font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em; }
          .detail-field dd { margin-top: 0.25rem; }
          .skills { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.25rem; }
          .skill-tag { background: #1c3a5f; color: #58a6ff; padding: 0.2rem 0.6rem; border-radius: 3px; font-size: 0.8rem; }
          .reasoning { background: #1c1f26; padding: 1rem; border-radius: 6px; margin-top: 0.5rem; border-left: 3px solid #58a6ff; }

          .pagination { display: flex; gap: 0.5rem; margin-top: 1rem; justify-content: center; }
          .pagination button { background: #1c1f26; border: 1px solid #333; color: #e1e1e6; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; }
          .pagination button:hover { background: #238636; border-color: #238636; }
          .pagination button.active { background: #238636; border-color: #238636; }

          .htmx-indicator { display: none; }
          .htmx-request .htmx-indicator { display: inline; }
          .htmx-request.htmx-indicator { display: inline; }
        </style>
      </head>
      <body>
        <div class="container">
          ${raw(content)}
        </div>
      </body>
    </html>`.toString();
}

export function listingTable(listings: Listing[], page: number, totalPages: number): string {
  const rows = listings
    .map(
      (l) => html`<tr>
        <td><a href="/listings/${l.id}">${l.title}</a></td>
        <td>${l.company}</td>
        <td>${l.location}</td>
        <td><span class="score" style="color: ${scoreColor(l.fit_score)}">${scoreDisplay(l.fit_score)}</span></td>
        <td>${l.salary}</td>
        <td><span class="badge">${l.source}</span></td>
        <td>${formatDate(l.posted_at)}</td>
      </tr>`,
    )
    .join("\n");

  const pagination = totalPages > 1
    ? html`<div class="pagination">
        ${Array.from({ length: totalPages }, (_, i) => i + 1)
          .map(
            (p) => html`<button
              hx-get="/listings?page=${p}"
              hx-target="#listing-results"
              hx-swap="innerHTML"
              class="${p === page ? "active" : ""}"
            >${p}</button>`,
          )
          .join("")}
      </div>`
    : "";

  return html`<table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Company</th>
          <th>Location</th>
          <th>Score</th>
          <th>Salary</th>
          <th>Source</th>
          <th>Posted</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
    ${pagination}`.toString();
}

export function listingDetail(listing: Listing): string {
  const enriched = listing.enriched_json || {};
  const skills = (enriched.skills as string[]) || [];
  const techStack = (enriched.tech_stack as string[]) || [];
  const reasoning = (enriched.reasoning as string) || "";
  const experienceLevel = (enriched.experience_level as string) || "—";
  const remotePolicy = (enriched.remote_policy as string) || "—";
  const summary = (enriched.summary as string) || "";

  return html`<div class="detail">
      <h2>${listing.title}</h2>
      <p><a href="${listing.url}" target="_blank">View original listing</a></p>

      <div class="detail-grid">
        <dl class="detail-field">
          <dt>Company</dt>
          <dd>${listing.company}</dd>
        </dl>
        <dl class="detail-field">
          <dt>Location</dt>
          <dd>${listing.location}</dd>
        </dl>
        <dl class="detail-field">
          <dt>Salary</dt>
          <dd>${listing.salary || "—"}</dd>
        </dl>
        <dl class="detail-field">
          <dt>Fit Score</dt>
          <dd><span class="score" style="color: ${scoreColor(listing.fit_score)}">${scoreDisplay(listing.fit_score)}</span></dd>
        </dl>
        <dl class="detail-field">
          <dt>Experience Level</dt>
          <dd>${experienceLevel}</dd>
        </dl>
        <dl class="detail-field">
          <dt>Remote Policy</dt>
          <dd>${remotePolicy}</dd>
        </dl>
        <dl class="detail-field">
          <dt>Source</dt>
          <dd><span class="badge">${listing.source}</span></dd>
        </dl>
        <dl class="detail-field">
          <dt>Posted</dt>
          <dd>${formatDate(listing.posted_at)}</dd>
        </dl>
      </div>

      ${
        skills.length > 0
          ? html`<div style="margin-top: 1rem;">
              <dt style="font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em;">Skills</dt>
              <div class="skills">${skills.map((s) => html`<span class="skill-tag">${s}</span>`).join("")}</div>
            </div>`
          : ""
      }

      ${
        techStack.length > 0
          ? html`<div style="margin-top: 1rem;">
              <dt style="font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em;">Tech Stack</dt>
              <div class="skills">${techStack.map((t) => html`<span class="skill-tag">${t}</span>`).join("")}</div>
            </div>`
          : ""
      }

      ${summary ? html`<div style="margin-top: 1rem;"><dt style="font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em;">AI Summary</dt><p style="margin-top: 0.25rem;">${summary}</p></div>` : ""}

      ${reasoning ? html`<div style="margin-top: 1rem;"><dt style="font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em;">Fit Reasoning</dt><div class="reasoning">${reasoning}</div></div>` : ""}
    </div>
    <p><a href="/">&larr; Back to listings</a></p>`.toString();
}
