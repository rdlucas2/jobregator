package source_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func TestJobicyAdapter_Name(t *testing.T) {
	src := source.NewJobicySource(nil, "")
	if src.Name() != "jobicy" {
		t.Errorf("Name() = %q, want %q", src.Name(), "jobicy")
	}
}

func TestJobicyAdapter_MapsResponseToRawListings(t *testing.T) {
	fakeResp := map[string]interface{}{
		"jobs": []map[string]interface{}{
			{
				"id":               1234,
				"url":              "https://jobicy.com/jobs/1234",
				"jobTitle":         "Senior DevOps Engineer",
				"companyName":      "Acme Corp",
				"jobIndustry":      []string{"DevOps & Sysadmin"},
				"jobType":          "full-time",
				"jobGeo":           "USA",
				"jobLevel":         "Senior",
				"jobExcerpt":       "Short description",
				"jobDescription":   "<p>We need a <strong>DevOps</strong> engineer.</p>",
				"pubDate":          "2026-03-28T10:00:00+00:00",
				"annualSalaryMin":  "150000",
				"annualSalaryMax":  "200000",
				"salaryCurrency":   "USD",
			},
		},
	}

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(fakeResp)
	}))
	defer ts.Close()

	src := source.NewJobicySource(nil, "usa")
	src.SetBaseURL(ts.URL)

	listings, err := src.Fetch(context.Background(), source.SearchQuery{Term: "DevOps", LookbackHours: 48})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(listings) != 1 {
		t.Fatalf("got %d listings, want 1", len(listings))
	}

	l := listings[0]
	if l.Source != "jobicy" {
		t.Errorf("Source = %q, want %q", l.Source, "jobicy")
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
	if l.Location != "USA" {
		t.Errorf("Location = %q, want %q", l.Location, "USA")
	}
	if l.Salary != "$150000-$200000" {
		t.Errorf("Salary = %q, want %q", l.Salary, "$150000-$200000")
	}
	if l.URL != "https://jobicy.com/jobs/1234" {
		t.Errorf("URL = %q, want %q", l.URL, "https://jobicy.com/jobs/1234")
	}
	// Description should have HTML stripped
	if l.Description != "We need a DevOps engineer." {
		t.Errorf("Description = %q, want HTML stripped", l.Description)
	}
}

func TestJobicyAdapter_DeduplicatesAcrossIndustries(t *testing.T) {
	fakeResp := map[string]interface{}{
		"jobs": []map[string]interface{}{
			{
				"id":              1,
				"url":             "https://jobicy.com/jobs/1",
				"jobTitle":        "DevOps Engineer",
				"companyName":     "Acme",
				"jobGeo":          "USA",
				"jobDescription":  "Role",
				"pubDate":         "2026-03-28T10:00:00+00:00",
				"annualSalaryMin": "",
				"annualSalaryMax": "",
				"salaryCurrency":  "",
			},
		},
	}

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(fakeResp)
	}))
	defer ts.Close()

	src := source.NewJobicySource([]string{"dev-engineering", "devops-sysadmin"}, "")
	src.SetBaseURL(ts.URL)

	listings, err := src.Fetch(context.Background(), source.SearchQuery{Term: "DevOps"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if len(listings) != 1 {
		t.Fatalf("got %d listings, want 1 (deduplicated across industries)", len(listings))
	}
}

func TestJobicyAdapter_EmptyResults(t *testing.T) {
	fakeResp := map[string]interface{}{
		"jobs": []map[string]interface{}{},
	}

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(fakeResp)
	}))
	defer ts.Close()

	src := source.NewJobicySource(nil, "")
	src.SetBaseURL(ts.URL)

	listings, err := src.Fetch(context.Background(), source.SearchQuery{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(listings) != 0 {
		t.Fatalf("got %d listings, want 0", len(listings))
	}
}
