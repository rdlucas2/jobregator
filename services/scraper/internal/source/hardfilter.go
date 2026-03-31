package source

import (
	"log"
	"strconv"
	"strings"

	"github.com/rdlucas2/jobregator/services/scraper/internal/config"
)

// ApplyHardFilters removes listings that fail any configured hard filter.
// Filters with zero values are treated as disabled.
func ApplyHardFilters(listings []RawListing, filters config.HardFilters) []RawListing {
	var result []RawListing
	for _, l := range listings {
		if reason := failsFilter(l, filters); reason != "" {
			log.Printf("[filter] rejected %q (%s) from %s — %s", l.Title, l.ExternalID, l.Source, reason)
			continue
		}
		result = append(result, l)
	}
	return result
}

// failsFilter returns the name of the first filter the listing fails, or "" if it passes all.
func failsFilter(l RawListing, f config.HardFilters) string {
	if f.Remote {
		locationRemote := isRemote(l.Location, l.Source)
		contextRemote := isRemoteByContext(l.Title, l.Description)
		if !locationRemote && !contextRemote {
			return "not remote (location: " + l.Location + ")"
		}
		if (locationRemote || contextRemote) && descriptionContradictsRemote(l.Description) {
			return "description contradicts remote"
		}
	}

	if len(f.Countries) > 0 && !matchesCountry(l.Location, f.Countries) {
		return "country not in allowlist (location: " + l.Location + ")"
	}

	if f.MinSalary > 0 && !meetsMinSalary(l.Salary, f.MinSalary) {
		return "salary below minimum (salary: " + l.Salary + ")"
	}

	if len(f.ExcludeTitles) > 0 && matchesExcludedTitle(l.Title, f.ExcludeTitles) {
		return "excluded title"
	}

	return ""
}

// antiRemotePatterns are phrases in job descriptions that indicate a listing
// tagged as "remote" is actually hybrid or on-site.
var antiRemotePatterns = []string{
	"must come into",
	"must be in office",
	"must be on-site",
	"must be onsite",
	"required to be in office",
	"required to be on-site",
	"required to be onsite",
	"days per week in office",
	"days a week in office",
	"days in office",
	"days on-site",
	"days onsite",
	"days in the office",
	"hybrid role",
	"hybrid position",
	"hybrid work",
	"hybrid schedule",
	"on-site requirement",
	"onsite requirement",
	"in-office requirement",
	"relocation required",
	"must relocate",
	"must be located in",
	"must be based in",
	"must reside in",
	"office-based",
	"not remote",
	"not a remote",
	"no remote",
}

// remoteEquivalentLocations are location terms that imply remote even without
// the word "remote" (e.g., Remotive uses "Worldwide" for all listings).
var remoteEquivalentLocations = []string{
	"remote", "worldwide", "anywhere", "global",
}

// remoteByDefinitionSources are job sources where ALL listings are remote.
var remoteByDefinitionSources = []string{
	"remotive",
}

func isRemote(location string, jobSource string) bool {
	sourceLower := strings.ToLower(jobSource)
	for _, s := range remoteByDefinitionSources {
		if sourceLower == s {
			return true
		}
	}

	lower := strings.ToLower(location)
	for _, term := range remoteEquivalentLocations {
		if strings.Contains(lower, term) {
			return true
		}
	}
	return false
}

// isRemoteByContext checks title and description for remote indicators when
// the location field alone doesn't say "remote" (common with Adzuna).
func isRemoteByContext(title, description string) bool {
	titleLower := strings.ToLower(title)
	if strings.Contains(titleLower, "remote") {
		return true
	}
	descLower := strings.ToLower(description)
	remoteIndicators := []string{
		"100% remote",
		"fully remote",
		"remote position",
		"remote role",
		"remote opportunity",
		"work from home",
		"work from anywhere",
		"work remotely",
	}
	for _, indicator := range remoteIndicators {
		if strings.Contains(descLower, indicator) {
			return true
		}
	}
	return false
}

// descriptionContradictsRemote checks if the description contains
// anti-remote language that contradicts a "remote" location tag.
func descriptionContradictsRemote(description string) bool {
	lower := strings.ToLower(description)
	for _, pattern := range antiRemotePatterns {
		if strings.Contains(lower, pattern) {
			return true
		}
	}
	return false
}

func meetsMinSalary(salary string, minSalary int) bool {
	if salary == "" {
		return true // no data = don't filter
	}

	min := parseSalaryMin(salary)
	if min == 0 {
		return true // unparseable = don't filter
	}

	return min >= minSalary
}

// parseSalaryMin extracts the first number from a salary string like "$150000-$200000".
func parseSalaryMin(salary string) int {
	// Strip dollar signs and commas
	cleaned := strings.ReplaceAll(salary, "$", "")
	cleaned = strings.ReplaceAll(cleaned, ",", "")

	// Split on dash to get min
	parts := strings.SplitN(cleaned, "-", 2)
	if len(parts) == 0 {
		return 0
	}

	val, err := strconv.Atoi(strings.TrimSpace(parts[0]))
	if err != nil {
		return 0
	}
	return val
}

// globalLocations are location terms that imply the position is open to all countries.
var globalLocations = []string{
	"worldwide", "anywhere", "global",
}

// regionToCountries maps broad region names to the countries they include,
// so "Americas" matches a country filter for "US", "USA", "Canada", etc.
var regionToCountries = map[string][]string{
	"americas":      {"us", "usa", "united states", "canada", "brazil", "mexico"},
	"north america": {"us", "usa", "united states", "canada", "mexico"},
	"europe":        {"uk", "germany", "france", "spain", "netherlands", "ireland", "sweden", "poland"},
	"emea":          {"uk", "germany", "france", "spain", "netherlands", "ireland"},
}

func matchesCountry(location string, countries []string) bool {
	lower := strings.ToLower(location)

	// Global locations match any country
	for _, g := range globalLocations {
		if strings.Contains(lower, g) {
			return true
		}
	}

	// Check if a region in the location maps to one of the allowed countries
	for region, regionCountries := range regionToCountries {
		if strings.Contains(lower, region) {
			for _, allowed := range countries {
				allowedLower := strings.ToLower(allowed)
				for _, rc := range regionCountries {
					if rc == allowedLower {
						return true
					}
				}
			}
		}
	}

	// Direct country match
	for _, country := range countries {
		if strings.Contains(lower, strings.ToLower(country)) {
			return true
		}
	}
	return false
}

func matchesExcludedTitle(title string, excludes []string) bool {
	lower := strings.ToLower(title)
	for _, exclude := range excludes {
		if strings.Contains(lower, strings.ToLower(exclude)) {
			return true
		}
	}
	return false
}
