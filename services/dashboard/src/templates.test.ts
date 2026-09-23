import { describe, it, expect } from "vitest";
import { layout, listingTable, listingDetail, listingRow, chartsSection, scoreColor, scoreDisplay, formatDate, type Listing } from "./templates.js";
import type { ScoreBucket, DailyCount, TopCompany, SourceCount, FilterReasonCount, DailySourceCount } from "./db.js";

const fakeListing: Listing = {
  id: 1,
  source: "adzuna",
  external_id: "123",
  title: "Senior DevOps Engineer",
  company: "Acme Corp",
  location: "Remote, USA",
  url: "https://example.com/jobs/123",
  salary: "$150000-$200000",
  posted_at: "2026-03-28T10:00:00Z",
  fit_score: 0.85,
  enriched_json: {
    skills: ["Kubernetes", "Terraform", "CI/CD"],
    tech_stack: ["AWS", "Docker"],
    experience_level: "senior",
    remote_policy: "remote",
    summary: "Senior DevOps role focused on cloud infrastructure.",
    reasoning: "Strong match for K8s and Terraform.",
  },
};

describe("layout", () => {
  it("wraps content in full HTML document", () => {
    const result = layout("Test", "<p>Hello</p>");
    expect(result).toContain("<!doctype html>");
    expect(result).toContain("<title>Test</title>");
    expect(result).toContain("<p>Hello</p>");
    expect(result).toContain("htmx.org");
  });

  it("includes SSE extension script", () => {
    const result = layout("Test", "");
    expect(result).toContain("htmx-ext-sse");
  });
});

describe("scoreColor", () => {
  it("returns green for high scores", () => {
    expect(scoreColor(0.85)).toBe("#2ecc71");
  });
  it("returns yellow for mid scores", () => {
    expect(scoreColor(0.65)).toBe("#f1c40f");
  });
  it("returns red for low scores", () => {
    expect(scoreColor(0.3)).toBe("#e74c3c");
  });
  it("returns gray for null", () => {
    expect(scoreColor(null)).toBe("#999");
  });
});

describe("scoreDisplay", () => {
  it("formats score to two decimals", () => {
    expect(scoreDisplay(0.85)).toBe("0.85");
  });
  it("returns dash for null", () => {
    expect(scoreDisplay(null)).toBe("—");
  });
});

describe("formatDate", () => {
  it("formats ISO date string", () => {
    const result = formatDate("2026-03-28T10:00:00Z");
    expect(result).toContain("Mar");
    expect(result).toContain("28");
    expect(result).toContain("2026");
  });
  it("returns dash for empty string", () => {
    expect(formatDate("")).toBe("—");
  });
});

describe("listingRow", () => {
  it("renders a single table row", () => {
    const result = listingRow(fakeListing);
    expect(result).toContain("<tr>");
    expect(result).toContain("Senior DevOps Engineer");
    expect(result).toContain("Acme Corp");
    expect(result).toContain("0.85");
    expect(result).toContain("adzuna");
  });
});

describe("listingTable", () => {
  it("renders a table with listing data", () => {
    const result = listingTable([fakeListing], 1, 1);
    expect(result).toContain("Senior DevOps Engineer");
    expect(result).toContain("Acme Corp");
    expect(result).toContain("0.85");
    expect(result).toContain("adzuna");
  });

  it("renders sortable column headers", () => {
    const result = listingTable([fakeListing], 1, 1);
    expect(result).toContain('class="sortable"');
    expect(result).toContain("sort_by=title");
    expect(result).toContain("sort_by=company");
    expect(result).toContain("sort_by=fit_score");
    expect(result).toContain("sort_by=salary");
    expect(result).toContain("sort_by=posted_at");
  });

  it("shows active sort arrow", () => {
    const result = listingTable([fakeListing], 1, 1, { sortBy: "title", sortOrder: "asc" });
    expect(result).toContain("&#9650;"); // up arrow
  });

  it("renders SSE attributes on tbody", () => {
    const result = listingTable([fakeListing], 1, 1);
    expect(result).toContain('sse-connect="/events"');
    expect(result).toContain('sse-swap="new-listing"');
  });

  it("renders pagination when multiple pages", () => {
    const result = listingTable([fakeListing], 1, 3);
    expect(result).toContain('class="pagination"');
    expect(result).toContain("page=2");
    expect(result).toContain("page=3");
  });

  it("pagination preserves sort state", () => {
    const result = listingTable([fakeListing], 1, 2, { sortBy: "title", sortOrder: "asc" });
    expect(result).toContain("sort_by=title");
    expect(result).toContain("sort_order=asc");
  });

  it("omits pagination for single page", () => {
    const result = listingTable([fakeListing], 1, 1);
    expect(result).not.toContain('class="pagination"');
  });

  it("renders empty table gracefully", () => {
    const result = listingTable([], 1, 0);
    expect(result).toContain("<table>");
    expect(result).toContain("</tbody>");
  });
});

describe("chartsSection", () => {
  // chartsSection takes six positional chart datasets. Calling it directly
  // meant every existing test broke when charts 4-6 were added, without a
  // compile error — tsconfig excludes *.test.ts and vitest does not
  // typecheck, so the arity mismatch only surfaced as `undefined.map()` at
  // runtime. Naming the arguments keeps these tests stable as charts grow.
  function renderCharts(
    data: {
      scores?: ScoreBucket[];
      daily?: DailyCount[];
      companies?: TopCompany[];
      sources?: SourceCount[];
      reasons?: FilterReasonCount[];
      dailyBySource?: DailySourceCount[];
    } = {},
  ): string {
    return chartsSection(
      data.scores ?? [],
      data.daily ?? [],
      data.companies ?? [],
      data.sources ?? [],
      data.reasons ?? [],
      data.dailyBySource ?? [],
    );
  }

  it("renders score distribution bars", () => {
    const result = renderCharts({
      scores: [
        { label: "0.0-0.3", count: 5 },
        { label: "0.8-1.0", count: 10 },
      ],
    });
    expect(result).toContain("Score Distribution");
    expect(result).toContain("0.0-0.3");
    expect(result).toContain("0.8-1.0");
    expect(result).toContain("bar-fill");
  });

  it("renders daily counts", () => {
    const result = renderCharts({
      daily: [
        { date: "2026-03-28", count: 15 },
        { date: "2026-03-29", count: 20 },
      ],
    });
    expect(result).toContain("Listings Per Day");
    expect(result).toContain("Mar");
  });

  it("renders top companies", () => {
    const result = renderCharts({
      companies: [
        { company: "Acme Corp", count: 8 },
        { company: "Initech", count: 3 },
      ],
    });
    expect(result).toContain("Top Companies");
    expect(result).toContain("Acme Corp");
    expect(result).toContain("Initech");
  });

  it("truncates long company names", () => {
    const result = renderCharts({
      companies: [{ company: "Very Long Company Name Inc", count: 5 }],
    });
    expect(result).toContain("\u2026");
  });

  it("handles empty data gracefully", () => {
    const result = renderCharts();
    expect(result).toContain("charts");
    expect(result).toContain("Score Distribution");
  });

  it("renders listings by source", () => {
    const result = renderCharts({
      sources: [
        { source: "adzuna", total: 40, passed: 10, filtered: 30 },
        { source: "remotive", total: 10, passed: 8, filtered: 2 },
      ],
    });
    expect(result).toContain("adzuna");
    expect(result).toContain("remotive");
    expect(result).toContain("40");
  });

  it("renders pass rate per source as a percentage", () => {
    const result = renderCharts({
      sources: [{ source: "adzuna", total: 40, passed: 10, filtered: 30 }],
    });
    expect(result).toContain("25%");
  });

  it("does not divide by zero when a source has no listings", () => {
    const result = renderCharts({
      sources: [{ source: "jobicy", total: 0, passed: 0, filtered: 0 }],
    });
    expect(result).toContain("jobicy");
    expect(result).not.toContain("NaN");
  });

  it("renders filter reasons and truncates long ones", () => {
    const result = renderCharts({
      reasons: [
        { reason: "not remote (location: Austin, TX — onsite required)", count: 12 },
        { reason: "below salary", count: 3 },
      ],
    });
    expect(result).toContain("below salary");
    expect(result).toContain("\u2026");
    expect(result).toContain("12");
  });

  it("says so when nothing was filtered", () => {
    const result = renderCharts({ reasons: [] });
    expect(result).toContain("No filtered listings");
  });

  it("renders daily counts broken down by source", () => {
    const result = renderCharts({
      dailyBySource: [
        { date: "2026-03-28", source: "adzuna", count: 5 },
        { date: "2026-03-28", source: "remotive", count: 3 },
        { date: "2026-03-29", source: "adzuna", count: 7 },
      ],
    });
    expect(result).toContain("bar-fill");
    expect(result).not.toContain("NaN");
  });
});

describe("listingDetail", () => {
  it("renders listing details with enrichment data", () => {
    const result = listingDetail(fakeListing);
    expect(result).toContain("Senior DevOps Engineer");
    expect(result).toContain("Acme Corp");
    expect(result).toContain("0.85");
    expect(result).toContain("Kubernetes");
    expect(result).toContain("Terraform");
    expect(result).toContain("AWS");
    expect(result).toContain("Strong match");
    expect(result).toContain("Senior DevOps role");
  });

  it("renders job description", () => {
    const withDesc: Listing = { ...fakeListing, description: "We are looking for a DevOps engineer to manage our cloud infrastructure." };
    const result = listingDetail(withDesc);
    expect(result).toContain("Description");
    expect(result).toContain("manage our cloud infrastructure");
  });

  it("handles listing with no enrichment", () => {
    const bare: Listing = { ...fakeListing, enriched_json: null, fit_score: null };
    const result = listingDetail(bare);
    expect(result).toContain("Senior DevOps Engineer");
    expect(result).toContain("—"); // null score display
  });
});
