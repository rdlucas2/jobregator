import { html, raw } from "hono/html";
import type { ScoreBucket, DailyCount, TopCompany } from "./db.js";

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
  description?: string;
}

export function scoreColor(score: number | null): string {
  if (score === null) return "#999";
  if (score >= 0.8) return "#2ecc71";
  if (score >= 0.6) return "#f1c40f";
  return "#e74c3c";
}

export function scoreDisplay(score: number | null): string {
  if (score === null) return "—";
  return score.toFixed(2);
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function listingRow(l: Listing): string {
  return html`<tr>
    <td><a href="/listings/${l.id}">${l.title}</a></td>
    <td>${l.company}</td>
    <td>${l.location}</td>
    <td><span class="score" style="color: ${scoreColor(l.fit_score)}">${scoreDisplay(l.fit_score)}</span></td>
    <td>${l.salary}</td>
    <td><span class="badge">${l.source}</span></td>
    <td>${formatDate(l.posted_at)}</td>
  </tr>`.toString();
}

export function layout(title: string, content: string): string {
  return html`<!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>${title}</title>
        <script src="https://unpkg.com/htmx.org@2.0.4"></script>
        <script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"></script>
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

          .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
          .chart-card { background: #161b22; border-radius: 8px; padding: 1rem; }
          .chart-card h3 { font-size: 0.85rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; }
          .bar-chart { display: flex; flex-direction: column; gap: 0.4rem; }
          .bar-row { display: flex; align-items: center; gap: 0.5rem; }
          .bar-label { width: 70px; font-size: 0.8rem; color: #aaa; text-align: right; flex-shrink: 0; }
          .bar-track { flex: 1; height: 20px; background: #1c1f26; border-radius: 3px; overflow: hidden; }
          .bar-fill { height: 100%; border-radius: 3px; min-width: 2px; transition: width 0.3s; }
          .bar-value { width: 35px; font-size: 0.8rem; color: #e1e1e6; }

          th.sortable { cursor: pointer; user-select: none; }
          th.sortable:hover { color: #58a6ff; }
          th .sort-arrow { font-size: 0.7rem; margin-left: 0.3rem; }

          @keyframes flash-new { from { background: #1a3a2a; } to { background: transparent; } }
          tr.new-row { animation: flash-new 2s ease-out; }

          .live-badge { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #2ecc71; margin-right: 0.4rem; animation: pulse 2s infinite; }
          @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

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

export interface SortState {
  sortBy: string;
  sortOrder: string;
}

function sortHeader(label: string, column: string, sort: SortState): string {
  const isActive = sort.sortBy === column;
  const nextOrder = isActive && sort.sortOrder === "desc" ? "asc" : isActive && sort.sortOrder === "asc" ? "desc" : "desc";
  const arrow = isActive ? (sort.sortOrder === "asc" ? " &#9650;" : " &#9660;") : "";
  return html`<th class="sortable"
    hx-get="/listings?sort_by=${column}&sort_order=${nextOrder}"
    hx-target="#listing-results"
    hx-swap="innerHTML"
    hx-include=".filters"
  >${label}<span class="sort-arrow">${raw(arrow)}</span></th>`.toString();
}

export function listingTable(listings: Listing[], page: number, totalPages: number, sort: SortState = { sortBy: "fit_score", sortOrder: "desc" }): string {
  const rows = listings.map((l) => listingRow(l)).join("\n");

  const pagination = totalPages > 1
    ? html`<div class="pagination">
        ${raw(Array.from({ length: totalPages }, (_, i) => i + 1)
          .map(
            (p) => html`<button
              hx-get="/listings?page=${p}&sort_by=${sort.sortBy}&sort_order=${sort.sortOrder}"
              hx-target="#listing-results"
              hx-swap="innerHTML"
              hx-include=".filters"
              class="${p === page ? "active" : ""}"
            >${p}</button>`,
          )
          .join(""))}
      </div>`
    : "";

  return html`<table>
      <thead>
        <tr>
          ${raw(sortHeader("Title", "title", sort))}
          ${raw(sortHeader("Company", "company", sort))}
          ${raw(sortHeader("Location", "location", sort))}
          ${raw(sortHeader("Score", "fit_score", sort))}
          ${raw(sortHeader("Salary", "salary", sort))}
          ${raw(sortHeader("Source", "source", sort))}
          ${raw(sortHeader("Posted", "posted_at", sort))}
        </tr>
      </thead>
      <tbody id="listing-tbody"
             hx-ext="sse"
             sse-connect="/events"
             sse-swap="new-listing"
             hx-swap="afterbegin">
        ${raw(rows)}
      </tbody>
    </table>
    ${pagination}`.toString();
}

const scoreColors: Record<string, string> = {
  "0.0-0.3": "#e74c3c",
  "0.3-0.6": "#f1c40f",
  "0.6-0.8": "#e67e22",
  "0.8-1.0": "#2ecc71",
  "Unscored": "#555",
};

export function chartsSection(scores: ScoreBucket[], daily: DailyCount[], topCompanies: TopCompany[]): string {
  const maxScore = Math.max(...scores.map((s) => Number(s.count)), 1);
  const scoreChart = scores
    .map((s) => {
      const pct = (Number(s.count) / maxScore) * 100;
      const color = scoreColors[s.label] ?? "#58a6ff";
      return `<div class="bar-row"><span class="bar-label">${s.label}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${color}"></div></div><span class="bar-value">${s.count}</span></div>`;
    })
    .join("");

  const maxDaily = Math.max(...daily.map((d) => Number(d.count)), 1);
  const dailyChart = daily
    .map((d) => {
      const pct = (Number(d.count) / maxDaily) * 100;
      const label = new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" });
      return `<div class="bar-row"><span class="bar-label">${label}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:#58a6ff"></div></div><span class="bar-value">${d.count}</span></div>`;
    })
    .join("");

  const maxCompany = Math.max(...topCompanies.map((c) => Number(c.count)), 1);
  const companyChart = topCompanies
    .map((c) => {
      const pct = (Number(c.count) / maxCompany) * 100;
      return `<div class="bar-row"><span class="bar-label" style="width:120px" title="${c.company}">${c.company.length > 15 ? c.company.slice(0, 14) + "…" : c.company}</span><div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:#9b59b6"></div></div><span class="bar-value">${c.count}</span></div>`;
    })
    .join("");

  return `<div class="charts">
    <div class="chart-card"><h3>Score Distribution</h3><div class="bar-chart">${scoreChart}</div></div>
    <div class="chart-card"><h3>Listings Per Day</h3><div class="bar-chart">${dailyChart}</div></div>
    <div class="chart-card"><h3>Top Companies</h3><div class="bar-chart">${companyChart}</div></div>
  </div>`;
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
              <div class="skills">${raw(skills.map((s) => html`<span class="skill-tag">${s}</span>`).join(""))}</div>
            </div>`
          : ""
      }

      ${
        techStack.length > 0
          ? html`<div style="margin-top: 1rem;">
              <dt style="font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em;">Tech Stack</dt>
              <div class="skills">${raw(techStack.map((t) => html`<span class="skill-tag">${t}</span>`).join(""))}</div>
            </div>`
          : ""
      }

      ${summary ? html`<div style="margin-top: 1rem;"><dt style="font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em;">AI Summary</dt><p style="margin-top: 0.25rem;">${summary}</p></div>` : ""}

      ${reasoning ? html`<div style="margin-top: 1rem;"><dt style="font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.05em;">Fit Reasoning</dt><div class="reasoning">${reasoning}</div></div>` : ""}
    </div>
    <p><a href="/">&larr; Back to listings</a></p>`.toString();
}
