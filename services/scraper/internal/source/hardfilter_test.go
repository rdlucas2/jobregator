package source_test

import (
	"testing"
	"time"

	"github.com/rdlucas2/jobregator/services/scraper/internal/config"
	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func newListing(title, location, salary string) source.RawListing {
	return source.RawListing{
		Source:     "adzuna",
		ExternalID: "1",
		Title:      title,
		Company:    "Acme",
		Location:   location,
		Salary:     salary,
		PostedAt:   time.Now(),
	}
}

func newRemotiveListing(title, location, salary string) source.RawListing {
	l := newListing(title, location, salary)
	l.Source = "remotive"
	return l
}

func newListingWithDesc(title, location, salary, description string) source.RawListing {
	l := newListing(title, location, salary)
	l.Description = description
	return l
}

func TestApplyHardFilters_RemoteOnly_TagsNonRemote(t *testing.T) {
	filters := config.HardFilters{Remote: true}
	listings := []source.RawListing{
		newListing("DevOps Engineer", "Remote", "$150000-$200000"),
		newListing("DevOps Engineer", "Remote, US", "$150000-$200000"),
		newListing("DevOps Engineer", "New York, NY", "$150000-$200000"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if len(result) != 3 {
		t.Fatalf("got %d listings, want 3 (all returned)", len(result))
	}
	if source.CountPassed(result) != 2 {
		t.Fatalf("passed %d listings, want 2 (only remote)", source.CountPassed(result))
	}
	if result[2].FilterReason == "" {
		t.Error("expected non-remote listing to have filter reason")
	}
}

func TestApplyHardFilters_RemoteFalse_KeepsAll(t *testing.T) {
	filters := config.HardFilters{Remote: false}
	listings := []source.RawListing{
		newListing("DevOps Engineer", "Remote", "$150000-$200000"),
		newListing("DevOps Engineer", "New York, NY", "$150000-$200000"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 2 {
		t.Fatalf("passed %d, want 2 (remote filter disabled)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_MinSalary_TagsLowPay(t *testing.T) {
	filters := config.HardFilters{MinSalary: 150000}
	listings := []source.RawListing{
		newListing("Senior DevOps", "Remote", "$160000-$200000"),
		newListing("Junior DevOps", "Remote", "$80000-$100000"),
		newListing("DevOps Engineer", "Remote", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 2 {
		t.Fatalf("passed %d, want 2 (filter low salary, keep unknown)", source.CountPassed(result))
	}
	if result[0].FilterReason != "" {
		t.Errorf("$160k listing should pass, got reason: %q", result[0].FilterReason)
	}
	if result[1].FilterReason == "" {
		t.Error("$80k listing should be tagged")
	}
	if result[2].FilterReason != "" {
		t.Errorf("empty salary listing should pass, got reason: %q", result[2].FilterReason)
	}
}

func TestApplyHardFilters_MinSalaryZero_KeepsAll(t *testing.T) {
	filters := config.HardFilters{MinSalary: 0}
	listings := []source.RawListing{
		newListing("DevOps", "Remote", "$50000-$60000"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 1 {
		t.Fatalf("passed %d, want 1 (no salary filter)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_ExcludeTitles_TagsMatches(t *testing.T) {
	filters := config.HardFilters{ExcludeTitles: []string{"Junior", "Intern"}}
	listings := []source.RawListing{
		newListing("Senior DevOps Engineer", "Remote", ""),
		newListing("Junior DevOps Engineer", "Remote", ""),
		newListing("DevOps Intern", "Remote", ""),
		newListing("Platform Engineer", "Remote", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 2 {
		t.Fatalf("passed %d, want 2", source.CountPassed(result))
	}
	if result[1].FilterReason == "" {
		t.Error("Junior listing should be tagged")
	}
	if result[2].FilterReason == "" {
		t.Error("Intern listing should be tagged")
	}
}

func TestApplyHardFilters_ExcludeTitles_CaseInsensitive(t *testing.T) {
	filters := config.HardFilters{ExcludeTitles: []string{"junior"}}
	listings := []source.RawListing{
		newListing("JUNIOR DevOps Engineer", "Remote", ""),
		newListing("Senior DevOps Engineer", "Remote", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 1 {
		t.Fatalf("passed %d, want 1", source.CountPassed(result))
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
	if len(result) != 4 {
		t.Fatalf("got %d listings, want 4 (all returned)", len(result))
	}
	if source.CountPassed(result) != 1 {
		t.Fatalf("passed %d, want 1 (only first passes all filters)", source.CountPassed(result))
	}
	if result[0].FilterReason != "" {
		t.Errorf("first listing should pass, got reason: %q", result[0].FilterReason)
	}
}

func TestApplyHardFilters_RemoteDescription_TagsHybrid(t *testing.T) {
	filters := config.HardFilters{Remote: true}
	listings := []source.RawListing{
		newListingWithDesc("DevOps Engineer", "Remote", "", "Great role. Must come into our office 3 days a week."),
		newListingWithDesc("DevOps Engineer", "Remote", "", "Fully remote position with async team."),
		newListingWithDesc("DevOps Engineer", "Remote", "", "This is a hybrid role requiring on-site presence."),
		newListingWithDesc("DevOps Engineer", "Remote", "", "We offer hybrid and remote options for all employees."),
		newListingWithDesc("DevOps Engineer", "Remote", "", "Remote-first. We have offices but attendance is optional."),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 3 {
		t.Fatalf("passed %d, want 3 (filter fake-remote, keep 'hybrid' mention without 'hybrid role')", source.CountPassed(result))
	}
	if result[0].FilterReason == "" {
		t.Error("'must come into' listing should be tagged")
	}
	if result[1].FilterReason != "" {
		t.Error("'fully remote' listing should pass")
	}
	if result[2].FilterReason == "" {
		t.Error("'hybrid role' listing should be tagged")
	}
	if result[3].FilterReason != "" {
		t.Error("'hybrid and remote options' listing should pass")
	}
	if result[4].FilterReason != "" {
		t.Error("'remote-first' listing should pass")
	}
}

func TestApplyHardFilters_RemoteDescription_SkipsCheckWhenRemoteDisabled(t *testing.T) {
	filters := config.HardFilters{Remote: false}
	listings := []source.RawListing{
		newListingWithDesc("DevOps Engineer", "Remote", "", "Must come into our office 3 days a week."),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 1 {
		t.Fatalf("passed %d, want 1 (remote filter disabled, no description check)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_RemoteDescription_VariousPatterns(t *testing.T) {
	filters := config.HardFilters{Remote: true}

	patterns := []struct {
		desc     string
		filtered bool
	}{
		{"Must relocate to Austin, TX", true},
		{"3 days per week in office required", true},
		{"This is not a remote position despite the tag", true},
		{"Relocation required for this role", true},
		{"Must be based in the greater NYC area", true},
		{"Work from anywhere in the US", false},
		{"100% distributed team", false},
	}

	for _, tc := range patterns {
		listings := []source.RawListing{
			newListingWithDesc("Engineer", "Remote", "", tc.desc),
		}
		result := source.ApplyHardFilters(listings, filters)
		if tc.filtered && result[0].FilterReason == "" {
			t.Errorf("expected %q to be tagged as filtered", tc.desc)
		}
		if !tc.filtered && result[0].FilterReason != "" {
			t.Errorf("expected %q to pass through, got reason: %q", tc.desc, result[0].FilterReason)
		}
	}
}

func TestApplyHardFilters_Countries_TagsOutsideAllowlist(t *testing.T) {
	filters := config.HardFilters{Countries: []string{"US", "USA"}}
	listings := []source.RawListing{
		newListing("DevOps", "Remote, US", ""),
		newListing("DevOps", "Remote, USA", ""),
		newListing("DevOps", "London, UK", ""),
		newListing("DevOps", "Remote, Canada", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 2 {
		t.Fatalf("passed %d, want 2 (only US/USA)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_Countries_EmptyAllowsAll(t *testing.T) {
	filters := config.HardFilters{Countries: []string{}}
	listings := []source.RawListing{
		newListing("DevOps", "London, UK", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 1 {
		t.Fatalf("passed %d, want 1 (no country filter)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_Countries_CaseInsensitive(t *testing.T) {
	filters := config.HardFilters{Countries: []string{"us"}}
	listings := []source.RawListing{
		newListing("DevOps", "Remote, US", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 1 {
		t.Fatalf("passed %d, want 1 (case insensitive)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_RemotiveSource_TreatedAsRemote(t *testing.T) {
	filters := config.HardFilters{Remote: true}
	listings := []source.RawListing{
		newRemotiveListing("DevOps Engineer", "Worldwide", ""),
		newRemotiveListing("Platform Engineer", "Americas, Europe", ""),
		newRemotiveListing("SRE", "USA Only", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 3 {
		t.Fatalf("passed %d, want 3 (all remotive listings are remote by definition)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_WorldwideMatchesAnyCountry(t *testing.T) {
	filters := config.HardFilters{Countries: []string{"US"}}
	listings := []source.RawListing{
		newRemotiveListing("DevOps Engineer", "Worldwide", ""),
		newRemotiveListing("Platform Engineer", "Americas, Europe", ""),
		newListing("SRE", "London, UK", ""),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 2 {
		t.Fatalf("passed %d, want 2 (worldwide and americas match US)", source.CountPassed(result))
	}
}

func TestApplyHardFilters_RemotiveFullStack(t *testing.T) {
	filters := config.HardFilters{
		Remote:        true,
		Countries:     []string{"US"},
		MinSalary:     150000,
		ExcludeTitles: []string{"Junior"},
	}
	listings := []source.RawListing{
		newRemotiveListing("Senior DevOps", "Worldwide", ""),        // passes
		newRemotiveListing("Senior DevOps", "Americas", "$160,000"), // passes
		newRemotiveListing("Junior DevOps", "Worldwide", ""),        // fails: title
		newRemotiveListing("Senior DevOps", "Worldwide", "$80,000"), // fails: salary
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 2 {
		t.Fatalf("passed %d, want 2", source.CountPassed(result))
	}
}

func TestApplyHardFilters_EmptyFilters_KeepsAll(t *testing.T) {
	filters := config.HardFilters{}
	listings := []source.RawListing{
		newListing("Any Job", "Anywhere", "$1-$2"),
	}

	result := source.ApplyHardFilters(listings, filters)
	if source.CountPassed(result) != 1 {
		t.Fatalf("passed %d, want 1 (no filters applied)", source.CountPassed(result))
	}
}
