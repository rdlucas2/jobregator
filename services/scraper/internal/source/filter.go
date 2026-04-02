package source

import (
	"fmt"
	"log"
	"time"
)

// FilterByLookback tags listings posted outside the lookback window with a FilterReason.
// If lookbackHours is 0, all listings are returned untagged.
func FilterByLookback(listings []RawListing, lookbackHours int) []RawListing {
	if lookbackHours <= 0 {
		return listings
	}

	cutoff := time.Now().Add(-time.Duration(lookbackHours) * time.Hour)

	result := make([]RawListing, 0, len(listings))
	for _, l := range listings {
		if !l.PostedAt.After(cutoff) {
			reason := fmt.Sprintf("outside lookback (posted %s, cutoff %s)",
				l.PostedAt.Format(time.RFC3339), cutoff.Format(time.RFC3339))
			log.Printf("[lookback] rejected %q (%s) from %s — %s", l.Title, l.ExternalID, l.Source, reason)
			l.FilterReason = reason
		}
		result = append(result, l)
	}
	return result
}
