package main

import (
	"context"
	"log"
	"os"
	"strconv"
	"strings"

	"github.com/rdlucas2/jobregator/services/scraper/internal/config"
	"github.com/rdlucas2/jobregator/services/scraper/internal/publisher"
	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

func main() {
	profilePath := envOrDefault("PROFILE_PATH", "/config/profile.yaml")
	natsURL := envOrDefault("NATS_URL", "nats://localhost:4222")
	adzunaAppID := os.Getenv("ADZUNA_APP_ID")
	adzunaAppKey := os.Getenv("ADZUNA_APP_KEY")
	adzunaCountry := envOrDefault("ADZUNA_COUNTRY", "us")
	remotiveCategories := envOrDefault("REMOTIVE_CATEGORIES", "devops")
	lookbackHours := envOrDefaultInt("LOOKBACK_HOURS", 14)

	if adzunaAppID == "" || adzunaAppKey == "" {
		log.Println("warning: ADZUNA_APP_ID/KEY not set, Adzuna source disabled")
	}

	profile, err := config.LoadProfile(profilePath)
	if err != nil {
		log.Fatalf("loading profile: %v", err)
	}

	log.Printf("loaded profile with %d search terms", len(profile.SearchTerms))

	ctx := context.Background()

	pub, err := publisher.NewNATSPublisher(natsURL)
	if err != nil {
		log.Fatalf("connecting to nats: %v", err)
	}
	defer pub.Close()

	if err := pub.EnsureStream(ctx); err != nil {
		log.Fatalf("ensuring nats stream: %v", err)
	}

	var sources []source.JobSource
	if adzunaAppID != "" && adzunaAppKey != "" {
		sources = append(sources, source.NewAdzunaSource(adzunaAppID, adzunaAppKey, adzunaCountry))
	}

	var cats []string
	if remotiveCategories != "" {
		cats = strings.Split(remotiveCategories, ",")
	}
	sources = append(sources, source.NewRemotiveSource(cats))

	totalPublished := 0

	for _, src := range sources {
		for _, term := range profile.SearchTerms {
			log.Printf("[%s] searching for %q", src.Name(), term)

			listings, err := src.Fetch(ctx, source.SearchQuery{
				Term:          term,
				LookbackHours: lookbackHours,
			})
			if err != nil {
				log.Printf("[%s] error fetching %q: %v", src.Name(), term, err)
				continue
			}

			filtered := source.FilterByLookback(listings, lookbackHours)
			filtered = source.ApplyHardFilters(filtered, profile.HardFilters)
			log.Printf("[%s] got %d listings for %q (%d after filters)",
				src.Name(), len(listings), term, len(filtered))

			for _, l := range filtered {
				if err := pub.Publish(ctx, l); err != nil {
					log.Printf("[%s] error publishing %s: %v", src.Name(), l.ExternalID, err)
					continue
				}
				totalPublished++
			}
		}
	}

	log.Printf("done: published %d listings to NATS", totalPublished)
}

func envOrDefault(key, defaultVal string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultVal
}

func envOrDefaultInt(key string, defaultVal int) int {
	if v := os.Getenv(key); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			log.Printf("warning: invalid %s=%q, using default %d", key, v, defaultVal)
			return defaultVal
		}
		return n
	}
	return defaultVal
}

