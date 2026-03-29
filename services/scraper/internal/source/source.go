package source

import (
	"context"
	"time"
)

type SearchQuery struct {
	Term          string
	LookbackHours int
}

type RawListing struct {
	Source      string    `json:"source"`
	ExternalID  string    `json:"external_id"`
	Title       string    `json:"title"`
	Company     string    `json:"company"`
	Location    string    `json:"location"`
	Description string    `json:"description"`
	URL         string    `json:"url"`
	Salary      string    `json:"salary"`
	PostedAt    time.Time `json:"posted_at"`
}

type JobSource interface {
	Name() string
	Fetch(ctx context.Context, query SearchQuery) ([]RawListing, error)
}
