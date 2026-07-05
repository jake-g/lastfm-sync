# Last.fm Scraper

Scrape playcounts and history from Last.fm, match with YouTube Music tracks, and generate comprehensive Last.fm Pro visual analytics and reports.

## Overview

This module interacts with the Last.fm API to scrape user scrobble history, compute track/album playcounts, match YouTube Music tracks, and generate high-resolution visual analytics and markdown reports.

## Structure

```
lastfm/
├── lastfm_scrape_history.py        # API Scrobble scraper & trigger for analytics
├── lastfm_analytics.py             # Pro visual analytics & report generator
├── match_ytmusic_tracks_with_lastfm_playcounts.py # YTMusic playcount matcher
├── auth.py                         # Last.fm API credentials
├── README.md                       # Architecture & documentation
└── reports/                        # Analytics output directory
    ├── lastfm_summary_report.md    # Unified human-readable Markdown report
    ├── lastfm_genre_weights.json   # Canonical genre weights (used by redacted/)
    ├── lastfm_artist_stats.tsv     # Per-artist scrobble statistics
    ├── lastfm_timeline_stats.tsv   # Monthly listening timeline statistics
    ├── lastfm_tag_stats.tsv        # Tag weight scores and rankings
    ├── yearly/                     # Disk-cached completed past years (2020-2025)
    ├── eras/                       # Disk-cached completed 5-year eras
    └── plots/                      # 12 High-Resolution Visual Plot Charts
        ├── scrobbles_over_time.png # Monthly listening volume timeline
        ├── era_5year_comparison.png # Annual listening & discovery comparison
        ├── yearly_2020s_trends.png  # Multi-line 2020s monthly trend plot
        ├── listening_clock_24h.png  # 24-Hour listening clock distribution
        ├── listening_heatmap.png    # Day vs Hour heatmap (Inferno colormap)
        ├── seasonality_monthly.png  # Seasonal monthly distribution (Seasonal palette)
        ├── artist_discovery_rate.png # Annual new artist discovery rate
        ├── artist_diversity_timeline.png # Monthly unique artist cataloging
        ├── top_20_artists.png       # Top 20 most listened artists
        ├── top_15_albums.png        # Top 15 most scrobbled albums
        ├── top_15_tracks.png        # Top 15 most scrobbled tracks
        └── top_20_genres.png        # Top 20 genre & tag frequency weights
```

---

## Scripts & Entrypoints

### 1. `lastfm_scrape_history.py`

Fetches scrobbles from Last.fm, calculates playcounts, and automatically triggers `lastfm_analytics.run_analytics()` upon completion.

- **Features**:
  - Concurrent fetching using `requests-toolbelt` (with lazy fallback).
  - Calculates playcounts per track & top albums.
  - Automatically runs the visual analytics suite at the end.
- **Usage**:

  ```bash
  python lastfm_scrape_history.py
  ```

---

### 2. `lastfm_analytics.py`

Standalone visual analytics engine that processes scrobbles and playcounts data to produce 12 visual charts, disk-cached historical breakdowns, and a unified markdown report.

- **Features**:
  - **12 Visual Charts**: Seaborn & Matplotlib high-resolution plots saved in `reports/plots/`.
  - **Disk Caching**: Completed past years (`reports/yearly/`) and 5-year eras (`reports/eras/`) are cached to eliminate git churn on weekly runs.
  - **Genre Weights Export**: Outputs canonical `reports/lastfm_genre_weights.json` consumed by `redacted/` mining tools.
- **Usage**:

  ```bash
  python lastfm_analytics.py
  ```

---

### 3. `match_ytmusic_tracks_with_lastfm_playcounts.py`

Matches YouTube Music tracks with Last.fm playcounts to enrich the YouTube Music database.

- **Usage**:

  ```bash
  python match_ytmusic_tracks_with_lastfm_playcounts.py
  ```

---

## Authentication & Setup

Ensure `auth.py` contains valid Last.fm credentials:

```python
LASTFM_API_KEY = 'your_api_key'
LASTFM_USER_NAME = 'your_username'
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Highlight Changelog

- **July 2026**: Integrated Pro Visual Analytics suite with 12 plots, disk-cached historical timelines, and seasonal/inferno colormaps. Relocated `lastfm_genre_weights.json` to `reports/`.
- **May 2026**: Modularized Last.fm directory with CI workflows.
- **Aug 2025**: Performed Phase 2 refactor of the matching logic.
- **Sep 2024**: Updated playcount matching code and resolved critical bugs.
- **Dec 2023**: Added functionality to fetch top albums from Last.fm.
