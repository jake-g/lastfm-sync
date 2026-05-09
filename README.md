# Last.fm Scraper

Scrape playcounts and history from Last.fm and match with YouTube Music tracks.

## Overview

This module interacts with the Last.fm API to scrape user listening history (scrobbles) and calculate playcounts. It also provides a script to match YouTube Music tracks with Last.fm playcounts to enrich the YouTube Music database with listening statistics.

## Scripts

### 1. `lastfm_scrape_history.py`

Scrapes scrobbles from Last.fm and calculates playcounts.

- **Features**:
  - Fetches scrobbles concurrently using `requests-toolbelt`.
  - Calculates playcounts per track.
  - Analyzes top albums.
- **Usage**:

    ```bash
    python lastfm_scrape_history.py
    ```

- **Outputs**:
  - `tsvs/lastfm_scrobbles.tsv` (All scrobbles).
  - `tsvs/lastfm_playcounts.tsv` (Playcounts per track).
  - `tsvs/lastfm_top_albums.tsv` (Top albums by playcount).

### 2. `match_ytmusic_tracks_with_lastfm_playcounts.py`

Matches YouTube Music tracks with Last.fm playcounts.

- **Features**:
  - Uses a map to cache matches for faster re-runs.
  - Fuzzy matches tracks if not cached.
- **Usage**:

    ```bash
    python match_ytmusic_tracks_with_lastfm_playcounts.py
    ```

- **Outputs**:
  - Updates `../ytmusic/playlists/_ytmusic_lastfm_match_id_map.tsv`.
  - Updates `../ytmusic/playlists/_ytmusic_lastfm_playcount.tsv`.
  - Generates a merged database at `tsvs/ytmusic_all_database.tsv`.

## Shared Library

- `unify_lib.py`: Shared library for path normalization and matching.

## Authentication

Ensure `auth.py` contains your Last.fm credentials:

```python
LASTFM_API_KEY = 'your_api_key'
LASTFM_USER_NAME = 'your_username'
```

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```


## Highlight Changelog

- **May 2026**: Modularized Last.fm directory with CI workflows
- **Aug 2025**: Performed Phase 2 refactor of the matching logic
- **Sep 2024**: Updated playcount matching code and resolved critical bugs
- **Dec 2023**: Added functionality to fetch top albums from Last.fm
- **Oct 2022**: Initial implementation of Last.fm playcount matching
- **Mar 2022**: Added the original Last.fm history scraper
