package source_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func TestAdzunaAdapter_Name(t *testing.T) {
	a := source.NewAdzunaSource("id", "key", "us")
	if a.Name() != "adzuna" {
		t.Errorf("Name() = %q, want %q", a.Name(), "adzuna")
	}
}

func TestAdzunaAdapter_MapsResponseToRawListings(t *testing.T) {
	// Mock Adzuna API response
	response := map[string]any{
		"count": 1,
		"results": []map[string]any{
			{
				"id":          "129698749",
				"title":       "Senior DevOps Engineer",
				"description": "A great DevOps role...",
				"created":     "2026-03-28T18:07:39Z",
				"redirect_url": "https://adzuna.com/jobs/129698749",
				"salary_min":  150000.0,
				"salary_max":  200000.0,
				"company": map[string]any{
					"display_name": "Acme Corp",
				},
				"location": map[string]any{
					"display_name": "Remote, USA",
				},
			},
		},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	a := source.NewAdzunaSource("test-id", "test-key", "us")
	a.SetBaseURL(server.URL)

	listings, err := a.Fetch(context.Background(), source.SearchQuery{
		Term:          "DevOps Engineer",
		LookbackHours: 0,
	})
	if err != nil {
		t.Fatalf("Fetch() error = %v", err)
	}

	if len(listings) != 1 {
		t.Fatalf("got %d listings, want 1", len(listings))
	}

	l := listings[0]
	if l.Source != "adzuna" {
		t.Errorf("Source = %q, want %q", l.Source, "adzuna")
	}
	if l.ExternalID != "129698749" {
		t.Errorf("ExternalID = %q, want %q", l.ExternalID, "129698749")
	}
	if l.Title != "Senior DevOps Engineer" {
		t.Errorf("Title = %q, want %q", l.Title, "Senior DevOps Engineer")
	}
	if l.Company != "Acme Corp" {
		t.Errorf("Company = %q, want %q", l.Company, "Acme Corp")
	}
	if l.Location != "Remote, USA" {
		t.Errorf("Location = %q, want %q", l.Location, "Remote, USA")
	}
	if l.Description != "A great DevOps role..." {
		t.Errorf("Description = %q, want %q", l.Description, "A great DevOps role...")
	}
	if l.URL != "https://adzuna.com/jobs/129698749" {
		t.Errorf("URL = %q, want %q", l.URL, "https://adzuna.com/jobs/129698749")
	}
	if l.Salary != "$150000-$200000" {
		t.Errorf("Salary = %q, want %q", l.Salary, "$150000-$200000")
	}
	expectedTime, _ := time.Parse(time.RFC3339, "2026-03-28T18:07:39Z")
	if !l.PostedAt.Equal(expectedTime) {
		t.Errorf("PostedAt = %v, want %v", l.PostedAt, expectedTime)
	}
}

func TestAdzunaAdapter_EmptyResults(t *testing.T) {
	response := map[string]any{
		"count":   0,
		"results": []map[string]any{},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	a := source.NewAdzunaSource("test-id", "test-key", "us")
	a.SetBaseURL(server.URL)

	listings, err := a.Fetch(context.Background(), source.SearchQuery{Term: "Nonexistent"})
	if err != nil {
		t.Fatalf("Fetch() error = %v", err)
	}
	if len(listings) != 0 {
		t.Errorf("got %d listings, want 0", len(listings))
	}
}
