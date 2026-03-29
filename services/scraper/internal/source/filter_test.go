package source_test

import (
	"testing"
	"time"

	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func TestFilterByLookback_IncludesRecentListings(t *testing.T) {
	now := time.Now()
	listings := []source.RawListing{
		{ExternalID: "recent", PostedAt: now.Add(-2 * time.Hour)},
		{ExternalID: "old", PostedAt: now.Add(-48 * time.Hour)},
		{ExternalID: "also-recent", PostedAt: now.Add(-10 * time.Hour)},
	}

	filtered := source.FilterByLookback(listings, 14)

	if len(filtered) != 2 {
		t.Fatalf("got %d listings, want 2", len(filtered))
	}
	if filtered[0].ExternalID != "recent" {
		t.Errorf("filtered[0].ExternalID = %q, want %q", filtered[0].ExternalID, "recent")
	}
	if filtered[1].ExternalID != "also-recent" {
		t.Errorf("filtered[1].ExternalID = %q, want %q", filtered[1].ExternalID, "also-recent")
	}
}

func TestFilterByLookback_ZeroHoursReturnsAll(t *testing.T) {
	now := time.Now()
	listings := []source.RawListing{
		{ExternalID: "a", PostedAt: now.Add(-100 * time.Hour)},
		{ExternalID: "b", PostedAt: now.Add(-1 * time.Hour)},
	}

	filtered := source.FilterByLookback(listings, 0)
	if len(filtered) != 2 {
		t.Fatalf("got %d listings, want 2 (zero hours means no filter)", len(filtered))
	}
}

func TestFilterByLookback_EmptyInput(t *testing.T) {
	filtered := source.FilterByLookback(nil, 14)
	if len(filtered) != 0 {
		t.Fatalf("got %d listings, want 0", len(filtered))
	}
}
