package source

import "time"

// FilterByLookback returns only listings posted within the last lookbackHours.
// If lookbackHours is 0, all listings are returned.
func FilterByLookback(listings []RawListing, lookbackHours int) []RawListing {
	if lookbackHours <= 0 {
		return listings
	}

	cutoff := time.Now().Add(-time.Duration(lookbackHours) * time.Hour)

	var filtered []RawListing
	for _, l := range listings {
		if l.PostedAt.After(cutoff) {
			filtered = append(filtered, l)
		}
	}
	return filtered
}
