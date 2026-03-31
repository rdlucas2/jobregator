package source_test

import (
	"testing"
	"time"

	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func TestFilterByLookback_TagsOldListings(t *testing.T) {
	now := time.Now()
	listings := []source.RawListing{
		{ExternalID: "recent", PostedAt: now.Add(-2 * time.Hour)},
		{ExternalID: "old", PostedAt: now.Add(-48 * time.Hour)},
		{ExternalID: "also-recent", PostedAt: now.Add(-10 * time.Hour)},
	}

	result := source.FilterByLookback(listings, 14)

	if len(result) != 3 {
		t.Fatalf("got %d listings, want 3 (all returned)", len(result))
	}
	if result[0].FilterReason != "" {
		t.Errorf("recent listing should pass, got reason: %q", result[0].FilterReason)
	}
	if result[1].FilterReason == "" {
		t.Error("old listing should be tagged")
	}
	if result[2].FilterReason != "" {
		t.Errorf("also-recent listing should pass, got reason: %q", result[2].FilterReason)
	}
}

func TestFilterByLookback_ZeroHoursReturnsAll(t *testing.T) {
	now := time.Now()
	listings := []source.RawListing{
		{ExternalID: "a", PostedAt: now.Add(-100 * time.Hour)},
		{ExternalID: "b", PostedAt: now.Add(-1 * time.Hour)},
	}

	result := source.FilterByLookback(listings, 0)
	if len(result) != 2 {
		t.Fatalf("got %d listings, want 2 (zero hours means no filter)", len(result))
	}
	for _, l := range result {
		if l.FilterReason != "" {
			t.Errorf("listing %s should not be tagged when lookback=0", l.ExternalID)
		}
	}
}

func TestFilterByLookback_EmptyInput(t *testing.T) {
	result := source.FilterByLookback(nil, 14)
	if len(result) != 0 {
		t.Fatalf("got %d listings, want 0", len(result))
	}
}
