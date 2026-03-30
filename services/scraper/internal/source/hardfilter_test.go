package source_test

import (
	"testing"
	"time"

	"github.com/rdlucas2/jobregator/services/scraper/internal/config"
	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func newListing(title, location, salary string) source.RawListing {
	return source.RawListing{
		ExternalID: "1",
		Title:      title,
		Company:    "Acme",
		Location:   location,
		Salary:     salary,
		PostedAt:   time.Now(),
	}
}

func TestApplyHardFilters_RemoteOnly_KeepsRemoteListings(t *testing.T) {
	filters := config.HardFilters{Remote: true}
	listings := []source.RawListing{
		newListing("DevOps Engineer", "Remote", "$150000-$200000"),
		newListing("DevOps Engineer", "Remote, US", "$150000-$200000"),
		newListing("DevOps Engineer", "New York, NY", "$150000-$200000"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 2 {
		t.Fatalf("got %d listings, want 2 (only remote)", len(result))
	}
}

func TestApplyHardFilters_RemoteFalse_KeepsAll(t *testing.T) {
	filters := config.HardFilters{Remote: false}
	listings := []source.RawListing{
		newListing("DevOps Engineer", "Remote", "$150000-$200000"),
		newListing("DevOps Engineer", "New York, NY", "$150000-$200000"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 2 {
		t.Fatalf("got %d listings, want 2 (remote filter disabled)", len(result))
	}
}

func TestApplyHardFilters_MinSalary_FiltersLowPay(t *testing.T) {
	filters := config.HardFilters{MinSalary: 150000}
	listings := []source.RawListing{
		newListing("Senior DevOps", "Remote", "$160000-$200000"),
		newListing("Junior DevOps", "Remote", "$80000-$100000"),
		newListing("DevOps Engineer", "Remote", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	// Keeps the $160k listing and the empty-salary listing (no data = don't filter)
	if len(result) != 2 {
		t.Fatalf("got %d listings, want 2 (filter low salary, keep unknown)", len(result))
	}
	if result[0].Title != "Senior DevOps" {
		t.Errorf("result[0].Title = %q, want %q", result[0].Title, "Senior DevOps")
	}
	if result[1].Title != "DevOps Engineer" {
		t.Errorf("result[1].Title = %q, want %q", result[1].Title, "DevOps Engineer")
	}
}

func TestApplyHardFilters_MinSalaryZero_KeepsAll(t *testing.T) {
	filters := config.HardFilters{MinSalary: 0}
	listings := []source.RawListing{
		newListing("DevOps", "Remote", "$50000-$60000"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 1 {
		t.Fatalf("got %d listings, want 1 (no salary filter)", len(result))
	}
}

func TestApplyHardFilters_ExcludeTitles_FiltersMatches(t *testing.T) {
	filters := config.HardFilters{ExcludeTitles: []string{"Junior", "Intern"}}
	listings := []source.RawListing{
		newListing("Senior DevOps Engineer", "Remote", ""),
		newListing("Junior DevOps Engineer", "Remote", ""),
		newListing("DevOps Intern", "Remote", ""),
		newListing("Platform Engineer", "Remote", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 2 {
		t.Fatalf("got %d listings, want 2", len(result))
	}
	if result[0].Title != "Senior DevOps Engineer" {
		t.Errorf("result[0].Title = %q, want %q", result[0].Title, "Senior DevOps Engineer")
	}
	if result[1].Title != "Platform Engineer" {
		t.Errorf("result[1].Title = %q, want %q", result[1].Title, "Platform Engineer")
	}
}

func TestApplyHardFilters_ExcludeTitles_CaseInsensitive(t *testing.T) {
	filters := config.HardFilters{ExcludeTitles: []string{"junior"}}
	listings := []source.RawListing{
		newListing("JUNIOR DevOps Engineer", "Remote", ""),
		newListing("Senior DevOps Engineer", "Remote", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 1 {
		t.Fatalf("got %d listings, want 1", len(result))
	}
}

func TestApplyHardFilters_CombinedFilters(t *testing.T) {
	filters := config.HardFilters{
		Remote:        true,
		MinSalary:     150000,
		ExcludeTitles: []string{"Junior"},
	}
	listings := []source.RawListing{
		newListing("Senior DevOps", "Remote", "$160000-$200000"),   // passes all
		newListing("Senior DevOps", "New York", "$160000-$200000"), // fails remote
		newListing("Senior DevOps", "Remote", "$80000-$100000"),    // fails salary
		newListing("Junior DevOps", "Remote", "$160000-$200000"),   // fails title
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 1 {
		t.Fatalf("got %d listings, want 1 (only first passes all filters)", len(result))
	}
	if result[0].Title != "Senior DevOps" || result[0].Location != "Remote" {
		t.Errorf("unexpected listing: %+v", result[0])
	}
}

func TestApplyHardFilters_EmptyFilters_KeepsAll(t *testing.T) {
	filters := config.HardFilters{}
	listings := []source.RawListing{
		newListing("Any Job", "Anywhere", "$1-$2"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 1 {
		t.Fatalf("got %d listings, want 1 (no filters applied)", len(result))
	}
}
