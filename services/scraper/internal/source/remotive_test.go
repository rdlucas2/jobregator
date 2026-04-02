package source_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func TestRemotiveAdapter_Name(t *testing.T) {
	src := source.NewRemotiveSource(nil)
	if src.Name() != "remotive" {
		t.Errorf("Name() = %q, want %q", src.Name(), "remotive")
	}
}

func TestRemotiveAdapter_MapsResponseToRawListings(t *testing.T) {
	fakeResp := map[string]interface{}{
		"jobs": []map[string]interface{}{
			{
				"id":                          1234,
				"url":                         "https://remotive.com/jobs/1234",
				"title":                       "Senior DevOps Engineer",
				"company_name":                "Acme Corp",
				"category":                    "DevOps",
				"candidate_required_location": "Worldwide",
				"salary":                      "$150,000 - $200,000",
				"description":                 "<p>We need a <strong>DevOps</strong> engineer.</p>",
				"publication_date":            "2026-03-28T10:00:00",
			},
		},
	}

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(fakeResp)
	}))
	defer ts.Close()

	src := source.NewRemotiveSource([]string{"devops"})
	src.SetBaseURL(ts.URL)

	listings, err := src.Fetch(context.Background(), source.SearchQuery{Term: "", LookbackHours: 14})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(listings) != 1 {
		t.Fatalf("got %d listings, want 1", len(listings))
	}

	l := listings[0]
	if l.Source != "remotive" {
		t.Errorf("Source = %q, want %q", l.Source, "remotive")
	}
	if l.ExternalID != "1234" {
		t.Errorf("ExternalID = %q, want %q", l.ExternalID, "1234")
	}
	if l.Title != "Senior DevOps Engineer" {
		t.Errorf("Title = %q, want %q", l.Title, "Senior DevOps Engineer")
	}
	if l.Company != "Acme Corp" {
		t.Errorf("Company = %q, want %q", l.Company, "Acme Corp")
	}
	if l.Location != "Worldwide" {
		t.Errorf("Location = %q, want %q", l.Location, "Worldwide")
	}
	if l.Salary != "$150,000 - $200,000" {
		t.Errorf("Salary = %q, want %q", l.Salary, "$150,000 - $200,000")
	}
	if l.URL != "https://remotive.com/jobs/1234" {
		t.Errorf("URL = %q, want %q", l.URL, "https://remotive.com/jobs/1234")
	}
	// Description should have HTML stripped
	if l.Description != "We need a DevOps engineer." {
		t.Errorf("Description = %q, want HTML stripped", l.Description)
	}
}

func TestRemotiveAdapter_FiltersBySearchTerm(t *testing.T) {
	fakeResp := map[string]interface{}{
		"jobs": []map[string]interface{}{
			{
				"id":                          1,
				"url":                         "https://remotive.com/jobs/1",
				"title":                       "Senior DevOps Engineer",
				"company_name":                "Acme",
				"candidate_required_location": "US",
				"salary":                      "",
				"description":                 "DevOps role",
				"publication_date":            "2026-03-28T10:00:00",
			},
			{
				"id":                          2,
				"url":                         "https://remotive.com/jobs/2",
				"title":                       "Frontend Developer",
				"company_name":                "Acme",
				"candidate_required_location": "US",
				"salary":                      "",
				"description":                 "React role",
				"publication_date":            "2026-03-28T10:00:00",
			},
		},
	}

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(fakeResp)
	}))
	defer ts.Close()

	src := source.NewRemotiveSource(nil)
	src.SetBaseURL(ts.URL)

	listings, err := src.Fetch(context.Background(), source.SearchQuery{Term: "DevOps"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(listings) != 1 {
		t.Fatalf("got %d listings, want 1 (filtered by term)", len(listings))
	}
	if listings[0].Title != "Senior DevOps Engineer" {
		t.Errorf("Title = %q, want %q", listings[0].Title, "Senior DevOps Engineer")
	}
}

func TestRemotiveAdapter_EmptyResults(t *testing.T) {
	fakeResp := map[string]interface{}{
		"jobs": []map[string]interface{}{},
	}

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(fakeResp)
	}))
	defer ts.Close()

	src := source.NewRemotiveSource(nil)
	src.SetBaseURL(ts.URL)

	listings, err := src.Fetch(context.Background(), source.SearchQuery{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(listings) != 0 {
		t.Fatalf("got %d listings, want 0", len(listings))
	}
}
