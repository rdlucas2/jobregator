package publisher

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/nats-io/nats.go"
	"github.com/nats-io/nats.go/jetstream"

	"github.com/rdlucas2/jobregator/services/scraper/internal/source"
)

const (
	StreamName = "JOBS"
	SubjectRaw = "jobs.raw"
)

type NATSPublisher struct {
	conn *nats.Conn
	js   jetstream.JetStream
}

func NewNATSPublisher(url string) (*NATSPublisher, error) {
	nc, err := nats.Connect(url)
	if err != nil {
		return nil, fmt.Errorf("connecting to nats: %w", err)
	}

	js, err := jetstream.New(nc)
	if err != nil {
		nc.Close()
		return nil, fmt.Errorf("creating jetstream context: %w", err)
	}

	return &NATSPublisher{conn: nc, js: js}, nil
}

func (p *NATSPublisher) EnsureStream(ctx context.Context) error {
	_, err := p.js.CreateOrUpdateStream(ctx, jetstream.StreamConfig{
		Name:     StreamName,
		Subjects: []string{"jobs.>"},
	})
	if err != nil {
		return fmt.Errorf("creating stream: %w", err)
	}
	return nil
}

func (p *NATSPublisher) Publish(ctx context.Context, listing source.RawListing) error {
	data, err := json.Marshal(listing)
	if err != nil {
		return fmt.Errorf("marshaling listing: %w", err)
	}

	_, err = p.js.Publish(ctx, SubjectRaw, data)
	if err != nil {
		return fmt.Errorf("publishing to %s: %w", SubjectRaw, err)
	}
	return nil
}

func (p *NATSPublisher) Close() {
	p.conn.Close()
}
