import { describe, it, expect } from "vitest";
import { layout, listingTable, listingDetail, type Listing } from "./templates.js";

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
});

describe("listingTable", () => {
  it("renders a table with listing data", () => {
    const result = listingTable([fakeListing], 1, 1);
    expect(result).toContain("Senior DevOps Engineer");
    expect(result).toContain("Acme Corp");
    expect(result).toContain("0.85");
    expect(result).toContain("adzuna");
  });

  it("renders pagination when multiple pages", () => {
    const result = listingTable([fakeListing], 1, 3);
    expect(result).toContain('class="pagination"');
    expect(result).toContain("page=2");
    expect(result).toContain("page=3");
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

  it("handles listing with no enrichment", () => {
    const bare: Listing = { ...fakeListing, enriched_json: null, fit_score: null };
    const result = listingDetail(bare);
    expect(result).toContain("Senior DevOps Engineer");
    expect(result).toContain("—"); // null score display
  });
});
