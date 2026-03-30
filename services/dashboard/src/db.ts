import postgres from "postgres";
import type { Listing } from "./templates.js";

let sql: ReturnType<typeof postgres>;

export function getDb(connectionString: string) {
  if (!sql) {
    sql = postgres(connectionString);
  }
  return sql;
}

export interface ListingsQuery {
  page?: number;
  perPage?: number;
  minScore?: number;
  maxScore?: number;
  search?: string;
  source?: string;
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

  const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

  const countResult = await db.unsafe(
    `SELECT COUNT(*) as total FROM job_listings ${where}`,
    params,
  );
  const total = Number(countResult[0].total);

  const listings = await db.unsafe(
    `SELECT id, source, external_id, title, company, location, url, salary,
            posted_at, fit_score, enriched_json
     FROM job_listings ${where}
     ORDER BY fit_score DESC NULLS LAST, posted_at DESC
     LIMIT $${paramIdx++} OFFSET $${paramIdx}`,
    [...params, perPage, offset],
  );

  return { listings: listings as unknown as Listing[], total };
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
