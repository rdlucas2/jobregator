package config_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/rdlucas2/jobregator/services/scraper/internal/config"
)

func TestLoadProfile_ParsesSearchTerms(t *testing.T) {
	dir := t.TempDir()
	profilePath := filepath.Join(dir, "profile.yaml")
	yaml := `search_terms:
  - "DevOps Engineer"
  - "Platform Engineer"
  - "SRE"

hard_filters:
  remote: true
  countries: ["US"]
  min_salary: 150000
  exclude_titles: ["Junior", "Intern"]

profile: |
  Senior DevOps / Platform Engineer with 10+ years experience.
`
	if err := os.WriteFile(profilePath, []byte(yaml), 0644); err != nil {
		t.Fatalf("failed to write test profile: %v", err)
	}

	p, err := config.LoadProfile(profilePath)
	if err != nil {
		t.Fatalf("LoadProfile() error = %v", err)
	}

	// Verify search terms
	expectedTerms := []string{"DevOps Engineer", "Platform Engineer", "SRE"}
	if len(p.SearchTerms) != len(expectedTerms) {
		t.Fatalf("SearchTerms length = %d, want %d", len(p.SearchTerms), len(expectedTerms))
	}
	for i, term := range expectedTerms {
		if p.SearchTerms[i] != term {
			t.Errorf("SearchTerms[%d] = %q, want %q", i, p.SearchTerms[i], term)
		}
	}

	// Verify hard filters
	if !p.HardFilters.Remote {
		t.Error("HardFilters.Remote = false, want true")
	}
	if len(p.HardFilters.Countries) != 1 || p.HardFilters.Countries[0] != "US" {
		t.Errorf("HardFilters.Countries = %v, want [US]", p.HardFilters.Countries)
	}
	if p.HardFilters.MinSalary != 150000 {
		t.Errorf("HardFilters.MinSalary = %d, want 150000", p.HardFilters.MinSalary)
	}
	if len(p.HardFilters.ExcludeTitles) != 2 {
		t.Errorf("HardFilters.ExcludeTitles length = %d, want 2", len(p.HardFilters.ExcludeTitles))
	}

	// Verify profile text
	if p.Profile == "" {
		t.Error("Profile is empty, want non-empty")
	}
}

func TestLoadProfile_FileNotFound(t *testing.T) {
	_, err := config.LoadProfile("/nonexistent/profile.yaml")
	if err == nil {
		t.Fatal("LoadProfile() expected error for missing file, got nil")
	}
}
