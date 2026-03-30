package source

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"time"
)

const defaultAdzunaBaseURL = "https://api.adzuna.com/v1/api/jobs"

type adzunaResponse struct {
	Count   int          `json:"count"`
	Results []adzunaJob  `json:"results"`
}

type adzunaJob struct {
	ID          string         `json:"id"`
	Title       string         `json:"title"`
	Description string         `json:"description"`
	Created     string         `json:"created"`
	RedirectURL string         `json:"redirect_url"`
	SalaryMin   float64        `json:"salary_min"`
	SalaryMax   float64        `json:"salary_max"`
	Company     adzunaCompany  `json:"company"`
	Location    adzunaLocation `json:"location"`
}

type adzunaCompany struct {
	DisplayName string `json:"display_name"`
}

type adzunaLocation struct {
	DisplayName string `json:"display_name"`
}

type AdzunaSource struct {
	appID   string
	appKey  string
	country string
	baseURL string
	client  *http.Client
}

func NewAdzunaSource(appID, appKey, country string) *AdzunaSource {
	return &AdzunaSource{
		appID:   appID,
		appKey:  appKey,
		country: country,
		baseURL: defaultAdzunaBaseURL,
		client:  &http.Client{Timeout: 30 * time.Second},
	}
}

func (a *AdzunaSource) SetBaseURL(u string) {
	a.baseURL = u
}

func (a *AdzunaSource) Name() string {
	return "adzuna"
}

func (a *AdzunaSource) Fetch(ctx context.Context, query SearchQuery) ([]RawListing, error) {
	params := url.Values{
		"app_id":           {a.appID},
		"app_key":          {a.appKey},
		"results_per_page": {"50"},
		"what":             {query.Term},
		"sort_by":          {"date"},
	}

	if query.LookbackHours > 0 {
		days := (query.LookbackHours + 23) / 24 // round up to days
		params.Set("max_days_old", fmt.Sprintf("%d", days))
	}

	reqURL := fmt.Sprintf("%s/%s/search/1?%s", a.baseURL, a.country, params.Encode())

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}

	resp, err := a.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching from adzuna: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("adzuna returned status %d", resp.StatusCode)
	}

	var apiResp adzunaResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("decoding adzuna response: %w", err)
	}

	listings := make([]RawListing, 0, len(apiResp.Results))
	for _, job := range apiResp.Results {
		postedAt, _ := time.Parse(time.RFC3339, job.Created)

		salary := ""
		if job.SalaryMin > 0 || job.SalaryMax > 0 {
			salary = fmt.Sprintf("$%.0f-$%.0f", job.SalaryMin, job.SalaryMax)
		}

		listings = append(listings, RawListing{
			Source:      "adzuna",
			ExternalID:  job.ID,
			Title:       job.Title,
			Company:     job.Company.DisplayName,
			Location:    job.Location.DisplayName,
			Description: job.Description,
			URL:         job.RedirectURL,
			Salary:      salary,
			PostedAt:    postedAt,
		})
	}

	return listings, nil
}
