package source

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

const defaultRemotiveBaseURL = "https://remotive.com/api/remote-jobs"

type remotiveResponse struct {
	Jobs []remotiveJob `json:"jobs"`
}

type remotiveJob struct {
	ID                        int    `json:"id"`
	URL                       string `json:"url"`
	Title                     string `json:"title"`
	CompanyName               string `json:"company_name"`
	Category                  string `json:"category"`
	CandidateRequiredLocation string `json:"candidate_required_location"`
	Salary                    string `json:"salary"`
	Description               string `json:"description"`
	PublicationDate           string `json:"publication_date"`
}

var htmlTagRe = regexp.MustCompile(`<[^>]*>`)

// stripHTML removes HTML tags and decodes common entities.
func stripHTML(s string) string {
	text := htmlTagRe.ReplaceAllString(s, " ")
	text = strings.ReplaceAll(text, "&amp;", "&")
	text = strings.ReplaceAll(text, "&lt;", "<")
	text = strings.ReplaceAll(text, "&gt;", ">")
	text = strings.ReplaceAll(text, "&quot;", "\"")
	text = strings.ReplaceAll(text, "&#39;", "'")
	text = strings.ReplaceAll(text, "&nbsp;", " ")
	// Collapse whitespace
	text = regexp.MustCompile(`\s+`).ReplaceAllString(text, " ")
	return strings.TrimSpace(text)
}

type RemotiveSource struct {
	categories []string
	baseURL    string
	client     *http.Client
}

// NewRemotiveSource creates a Remotive adapter. categories are Remotive category slugs
// (e.g. "devops", "software-development"). If empty, all categories are fetched.
func NewRemotiveSource(categories []string) *RemotiveSource {
	return &RemotiveSource{
		categories: categories,
		baseURL:    defaultRemotiveBaseURL,
		client:     &http.Client{Timeout: 30 * time.Second},
	}
}

func (r *RemotiveSource) SetBaseURL(u string) {
	r.baseURL = u
}

func (r *RemotiveSource) Name() string {
	return "remotive"
}

func (r *RemotiveSource) Fetch(ctx context.Context, query SearchQuery) ([]RawListing, error) {
	// Remotive doesn't support search terms directly, so we fetch by category
	// and filter by term client-side
	cats := r.categories
	if len(cats) == 0 {
		cats = []string{""}
	}

	var allListings []RawListing
	for _, cat := range cats {
		listings, err := r.fetchCategory(ctx, cat, query)
		if err != nil {
			return nil, err
		}
		allListings = append(allListings, listings...)
	}

	// Client-side filter by search term
	if query.Term != "" {
		termLower := strings.ToLower(query.Term)
		var filtered []RawListing
		for _, l := range allListings {
			if strings.Contains(strings.ToLower(l.Title), termLower) ||
				strings.Contains(strings.ToLower(l.Description), termLower) {
				filtered = append(filtered, l)
			}
		}
		return filtered, nil
	}

	return allListings, nil
}

func (r *RemotiveSource) fetchCategory(ctx context.Context, category string, query SearchQuery) ([]RawListing, error) {
	params := url.Values{
		"limit": {"50"},
	}
	if category != "" {
		params.Set("category", category)
	}

	reqURL := fmt.Sprintf("%s?%s", r.baseURL, params.Encode())

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}

	resp, err := r.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching from remotive: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("remotive returned status %d", resp.StatusCode)
	}

	var apiResp remotiveResponse
	if err := json.NewDecoder(resp.Body).Decode(&apiResp); err != nil {
		return nil, fmt.Errorf("decoding remotive response: %w", err)
	}

	listings := make([]RawListing, 0, len(apiResp.Jobs))
	for _, job := range apiResp.Jobs {
		postedAt, _ := time.Parse("2006-01-02T15:04:05", job.PublicationDate)

		listings = append(listings, RawListing{
			Source:      "remotive",
			ExternalID:  fmt.Sprintf("%d", job.ID),
			Title:       job.Title,
			Company:     job.CompanyName,
			Location:    job.CandidateRequiredLocation,
			Description: stripHTML(job.Description),
			URL:         job.URL,
			Salary:      job.Salary,
			PostedAt:    postedAt,
		})
	}

	return listings, nil
}
