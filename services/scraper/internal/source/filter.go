package source

import (
	"log"
	"time"
)

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
		} else {
			log.Printf("[lookback] rejected %q (%s) from %s — posted %s (cutoff %s)",
				l.Title, l.ExternalID, l.Source, l.PostedAt.Format(time.RFC3339), cutoff.Format(time.RFC3339))
		}
	}
	return filtered
}
