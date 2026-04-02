package source

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const defaultJobicyBaseURL = "https://jobicy.com/api/v2/remote-jobs"

type jobicyResponse struct {
	Jobs []jobicyJob `json:"jobs"`
}

type jobicyJob struct {
	ID              int      `json:"id"`
	URL             string   `json:"url"`
	JobTitle        string   `json:"jobTitle"`
	CompanyName     string   `json:"companyName"`
	JobIndustry     []string `json:"jobIndustry"`
	JobType         json.RawMessage `json:"jobType"`
	JobGeo          string   `json:"jobGeo"`
	JobLevel        string   `json:"jobLevel"`
	JobExcerpt      string   `json:"jobExcerpt"`
	JobDescription  string   `json:"jobDescription"`
	PubDate         string   `json:"pubDate"`
	AnnualSalaryMin string   `json:"annualSalaryMin"`
	AnnualSalaryMax string   `json:"annualSalaryMax"`
	SalaryCurrency  string   `json:"salaryCurrency"`
}

type JobicySource struct {
	industries []string
	geo        string
	baseURL    string
	client     *http.Client
	cache      []RawListing
}

// NewJobicySource creates a Jobicy adapter. industries are Jobicy industry slugs
// (e.g. "dev-engineering", "devops-sysadmin"). geo filters by geography (e.g. "usa").
func NewJobicySource(industries []string, geo string) *JobicySource {
	return &JobicySource{
		industries: industries,
		geo:        geo,
		baseURL:    defaultJobicyBaseURL,
		client:     &http.Client{Timeout: 30 * time.Second},
	}
}

func (j *JobicySource) SetBaseURL(u string) {
	j.baseURL = u
}

func (j *JobicySource) Name() string {
	return "jobicy"
}

func (j *JobicySource) Fetch(ctx context.Context, query SearchQuery) ([]RawListing, error) {
	// Cache results across search terms to avoid hitting rate limits.
	// Jobicy recommends max once per hour, so we fetch once and filter client-side.
	if j.cache == nil {
		if err := j.fetchAll(ctx); err != nil {
			return nil, err
		}
	}

	// Client-side filter by search term
	if query.Term == "" {
		return j.cache, nil
	}

	termLower := strings.ToLower(query.Term)
	var filtered []RawListing
	for _, l := range j.cache {
		if strings.Contains(strings.ToLower(l.Title), termLower) ||
			strings.Contains(strings.ToLower(l.Description), termLower) {
			filtered = append(filtered, l)
		}
	}
	return filtered, nil
}

func (j *JobicySource) fetchAll(ctx context.Context) error {
	industries := j.industries
	if len(industries) == 0 {
		industries = []string{""}
	}

	seen := make(map[int]bool)
	var allListings []RawListing
	for _, industry := range industries {
		params := url.Values{
			"count": {"50"},
		}
		if j.geo != "" {
			params.Set("geo", j.geo)
		}
		if industry != "" {
			params.Set("industry", industry)
		}

		listings, err := j.fetchWithParams(ctx, params, seen)
		if err != nil {
			return err
		}
		allListings = append(allListings, listings...)
	}

	j.cache = allListings
	return nil
}

func (j *JobicySource) fetchWithParams(ctx context.Context, params url.Values, seen map[int]bool) ([]RawListing, error) {
	reqURL := fmt.Sprintf("%s?%s", j.baseURL, params.Encode())

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}

	resp, err := j.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching from jobicy: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("jobicy returned status %d", resp.StatusCode)
	}

	var apiResp jobicyResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("decoding jobicy response: %w", err)
	}

	listings := make([]RawListing, 0, len(apiResp.Jobs))
	for _, job := range apiResp.Jobs {
		if seen[job.ID] {
			continue
		}
		seen[job.ID] = true

		postedAt, _ := time.Parse(time.RFC3339, job.PubDate)

		salary := ""
		if job.AnnualSalaryMin != "" && job.AnnualSalaryMax != "" {
			currency := job.SalaryCurrency
			if currency == "" {
				currency = "USD"
			}
			salary = fmt.Sprintf("%s%s-%s%s", currencySymbol(currency), job.AnnualSalaryMin, currencySymbol(currency), job.AnnualSalaryMax)
		} else if job.AnnualSalaryMin != "" {
			salary = fmt.Sprintf("%s%s+", currencySymbol(job.SalaryCurrency), job.AnnualSalaryMin)
		}

		listings = append(listings, RawListing{
			Source:      "jobicy",
			ExternalID:  fmt.Sprintf("%d", job.ID),
			Title:       job.JobTitle,
			Company:     job.CompanyName,
			Location:    job.JobGeo,
			Description: stripHTML(job.JobDescription),
			URL:         job.URL,
			Salary:      salary,
			PostedAt:    postedAt,
		})
	}

	return listings, nil
}

func currencySymbol(code string) string {
	switch strings.ToUpper(code) {
	case "USD":
		return "$"
	case "EUR":
		return "€"
	case "GBP":
		return "£"
	default:
		return code + " "
	}
}
