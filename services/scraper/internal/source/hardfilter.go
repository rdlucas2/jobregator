package source

import (
	"strconv"
	"strings"

	"github.com/rdlucas2/jobregator/services/scraper/internal/config"
)

// ApplyHardFilters removes listings that fail any configured hard filter.
// Filters with zero values are treated as disabled.
func ApplyHardFilters(listings []RawListing, filters config.HardFilters) []RawListing {
	var result []RawListing
	for _, l := range listings {
		if passesAllFilters(l, filters) {
			result = append(result, l)
		}
	}
	return result
}

func passesAllFilters(l RawListing, f config.HardFilters) bool {
	if f.Remote && !isRemote(l.Location) {
		return false
	}

	if f.MinSalary > 0 && !meetsMinSalary(l.Salary, f.MinSalary) {
		return false
	}

	if len(f.ExcludeTitles) > 0 && matchesExcludedTitle(l.Title, f.ExcludeTitles) {
		return false
	}

	return true
}

func isRemote(location string) bool {
	return strings.Contains(strings.ToLower(location), "remote")
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

func matchesExcludedTitle(title string, excludes []string) bool {
	lower := strings.ToLower(title)
	for _, exclude := range excludes {
		if strings.Contains(lower, strings.ToLower(exclude)) {
			return true
		}
	}
	return false
}
