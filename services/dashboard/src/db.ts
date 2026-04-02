import postgres from "postgres";
import type { Listing } from "./templates.js";

let sql: ReturnType<typeof postgres>;

export function getDb(connectionString: string) {
  if (!sql) {
    sql = postgres(connectionString);
  }
  return sql;
}

export type SortColumn = "title" | "company" | "location" | "fit_score" | "salary" | "source" | "posted_at";
export type SortOrder = "asc" | "desc";

export interface ListingsQuery {
  page?: number;
  perPage?: number;
  minScore?: number;
  maxScore?: number;
  minSalary?: number;
  maxSalary?: number;
  search?: string;
  source?: string;
  status?: "all" | "passed" | "filtered";
  sortBy?: SortColumn;
  sortOrder?: SortOrder;
}

export async function getListings(
  db: ReturnType<typeof postgres>,
  query: ListingsQuery = {},
): Promise<{ listings: Listing[]; total: number }> {
  const page = query.page ?? 1;
  const perPage = query.perPage ?? 25;
  const offset = (page - 1) * perPage;

  const conditions: string[] = [];
  const params: unknown[] = [];
  let paramIdx = 1;

  if (query.minScore !== undefined) {
    conditions.push(`fit_score >= $${paramIdx++}`);
    params.push(query.minScore);
  }
  if (query.maxScore !== undefined) {
    conditions.push(`fit_score <= $${paramIdx++}`);
    params.push(query.maxScore);
  }
  if (query.search) {
    conditions.push(`(title ILIKE $${paramIdx} OR company ILIKE $${paramIdx})`);
    params.push(`%${query.search}%`);
    paramIdx++;
  }
  if (query.source) {
    conditions.push(`source = $${paramIdx++}`);
    params.push(query.source);
  }
  if (query.status === "passed") {
    conditions.push(`filter_reason IS NULL`);
  } else if (query.status === "filtered") {
    conditions.push(`filter_reason IS NOT NULL`);
  }
  if (query.minSalary !== undefined) {
    conditions.push(`CAST(NULLIF(REGEXP_REPLACE(SPLIT_PART(salary, '-', 1), '[^0-9]', '', 'g'), '') AS INTEGER) >= $${paramIdx++}`);
    params.push(query.minSalary);
  }
  if (query.maxSalary !== undefined) {
    conditions.push(`CAST(NULLIF(REGEXP_REPLACE(SPLIT_PART(salary, '-', 2), '[^0-9]', '', 'g'), '') AS INTEGER) <= $${paramIdx++}`);
    params.push(query.maxSalary);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  const validSortColumns: Record<SortColumn, string> = {
    title: "title",
    company: "company",
    location: "location",
    fit_score: "fit_score",
    salary: "CAST(NULLIF(REGEXP_REPLACE(SPLIT_PART(salary, '-', 1), '[^0-9]', '', 'g'), '') AS INTEGER)",
    source: "source",
    posted_at: "posted_at",
  };
  const sortCol = validSortColumns[query.sortBy ?? "fit_score"] ?? "fit_score";
  const sortDir = query.sortOrder === "asc" ? "ASC" : "DESC";
  const nullsPos = sortDir === "DESC" ? "NULLS LAST" : "NULLS FIRST";
  const orderBy = `ORDER BY ${sortCol} ${sortDir} ${nullsPos}, posted_at DESC`;

  const countResult = await db.unsafe(
    `SELECT COUNT(*) as total FROM job_listings ${where}`,
    params,
  );
  const total = Number(countResult[0].total);

  const listings = await db.unsafe(
    `SELECT id, source, external_id, title, company, location, url, salary,
            posted_at, fit_score, enriched_json, filter_reason
     FROM job_listings ${where}
     ${orderBy}
     LIMIT $${paramIdx++} OFFSET $${paramIdx}`,
    [...params, perPage, offset],
  );

  return { listings: listings as unknown as Listing[], total };
}

export interface ScoreBucket {
  label: string;
  count: number;
}

export interface DailyCount {
  date: string;
  count: number;
}

export interface TopCompany {
  company: string;
  count: number;
}

export async function getScoreDistribution(
  db: ReturnType<typeof postgres>,
): Promise<ScoreBucket[]> {
  const result = await db`
    SELECT
      CASE
        WHEN fit_score IS NULL THEN 'Unscored'
        WHEN fit_score < 0.3 THEN '0.0-0.3'
        WHEN fit_score < 0.6 THEN '0.3-0.6'
        WHEN fit_score < 0.8 THEN '0.6-0.8'
        ELSE '0.8-1.0'
      END as label,
      COUNT(*) as count
    FROM job_listings
    GROUP BY label
    ORDER BY label
  `;
  return result as unknown as ScoreBucket[];
}

export async function getDailyCounts(
  db: ReturnType<typeof postgres>,
  days: number = 14,
): Promise<DailyCount[]> {
  const result = await db`
    SELECT DATE(posted_at) as date, COUNT(*) as count
    FROM job_listings
    WHERE posted_at >= NOW() - ${days + ' days'}::interval
    GROUP BY DATE(posted_at)
    ORDER BY date
  `;
  return result as unknown as DailyCount[];
}

export async function getTopCompanies(
  db: ReturnType<typeof postgres>,
  limit: number = 10,
): Promise<TopCompany[]> {
  const result = await db`
    SELECT company, COUNT(*) as count
    FROM job_listings
    WHERE fit_score IS NOT NULL
    GROUP BY company
    ORDER BY COUNT(*) DESC
    LIMIT ${limit}
  `;
  return result as unknown as TopCompany[];
}

export interface SourceCount {
  source: string;
  total: number;
  passed: number;
  filtered: number;
}

export async function getSourceCounts(
  db: ReturnType<typeof postgres>,
): Promise<SourceCount[]> {
  const result = await db`
    SELECT source,
           COUNT(*) as total,
           COUNT(*) FILTER (WHERE filter_reason IS NULL) as passed,
           COUNT(*) FILTER (WHERE filter_reason IS NOT NULL) as filtered
    FROM job_listings
    GROUP BY source
    ORDER BY total DESC
  `;
  return result as unknown as SourceCount[];
}

export interface FilterReasonCount {
  reason: string;
  count: number;
}

export async function getFilterReasonCounts(
  db: ReturnType<typeof postgres>,
): Promise<FilterReasonCount[]> {
  const result = await db`
    SELECT filter_reason as reason, COUNT(*) as count
    FROM job_listings
    WHERE filter_reason IS NOT NULL
    GROUP BY filter_reason
    ORDER BY count DESC
    LIMIT 10
  `;
  return result as unknown as FilterReasonCount[];
}

export interface DailySourceCount {
  date: string;
  source: string;
  count: number;
}

export async function getDailyCountsBySource(
  db: ReturnType<typeof postgres>,
  days: number = 14,
): Promise<DailySourceCount[]> {
  const result = await db`
    SELECT DATE(posted_at) as date, source, COUNT(*) as count
    FROM job_listings
    WHERE posted_at >= NOW() - ${days + ' days'}::interval
    GROUP BY DATE(posted_at), source
    ORDER BY date, source
  `;
  return result as unknown as DailySourceCount[];
}

export async function getSources(
  db: ReturnType<typeof postgres>,
): Promise<string[]> {
  const result = await db`SELECT DISTINCT source FROM job_listings ORDER BY source`;
  return result.map((r) => r.source as string);
}

export async function getListingById(
  db: ReturnType<typeof postgres>,
  id: number,
): Promise<Listing | null> {
  const result = await db`
    SELECT id, source, external_id, title, company, location, url, salary,
           posted_at, fit_score, enriched_json, description
    FROM job_listings
    WHERE id = ${id}
  `;
  if (result.length === 0) return null;
  return result[0] as unknown as Listing;
}
