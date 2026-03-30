package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type HardFilters struct {
	Remote        bool     `yaml:"remote"`
	Countries     []string `yaml:"countries"`
	MinSalary     int      `yaml:"min_salary"`
	ExcludeTitles []string `yaml:"exclude_titles"`
}

type Profile struct {
	SearchTerms []string    `yaml:"search_terms"`
	HardFilters HardFilters `yaml:"hard_filters"`
	Profile     string      `yaml:"profile"`
}

func LoadProfile(path string) (*Profile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading profile: %w", err)
	}

	var p Profile
	if err := yaml.Unmarshal(data, &p); err != nil {
		return nil, fmt.Errorf("parsing profile: %w", err)
	}

	return &p, nil
}
