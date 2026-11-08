"""Matches YouTube Music tracks against Last.fm playcounts."""

import argparse
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

import pandas as pd

# Root directory for unified music source outputs
OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'music-sources-unified')
)
if OUTPUT_DIR not in sys.path:
  sys.path.append(OUTPUT_DIR)

# isort: split
import unify_lib as uni

# Run Interval Threshold (90 days = 3 months default)
RUN_INTERVAL_DAYS = 90
JOB_NAME = 'ytmusic_lastfm_match'

LOG_EVERY = 500
DATE = time.strftime('%m-%d-%Y')

LASTFM_PLAYCOUNTS = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_playcounts.tsv')
YT_TRACK_DB_LATEST = os.path.join(
    OUTPUT_DIR, '../ytmusic/playlists/_tracks_db.tsv'
)
YT_TRACK_DB_OUT = os.path.join(OUTPUT_DIR, 'tsvs', 'ytmusic_all_database.tsv')
YT_LASTFM_MAP = os.path.join(
    OUTPUT_DIR, '../ytmusic/playlists/_ytmusic_lastfm_match_id_map.tsv'
)
YT_LASTFM_PLACYCOUNT = os.path.join(
    OUTPUT_DIR, '../ytmusic/playlists/_ytmusic_lastfm_playcount.tsv'
)

LOAD_LAST_MATCHES = True

YTB_CP_COLS = [
    'title',
    'album',
    'likeStatus',
    'duration',
    'artistId',
    'albumId',
    'playlists',
    'averageRating',
    'viewCount',
    'albumArtist',
    'albumYear',
    'albumTrackCount',
    'albumDuration',
    'albumType',
    'fuzzy_album_id',
    'fuzzy_id',
]

yt_no_lastfm_match_f = os.path.join(
    OUTPUT_DIR, 'logs', f'ytmusic_no_lastfm_match_{DATE}.tsv'
)
yt_playcounts_f = os.path.join(
    OUTPUT_DIR, 'logs', f'ytmusic_lastfm_playcounts_{DATE}.tsv'
)
yt_lastfm_id_map_f = os.path.join(
    OUTPUT_DIR, 'logs', f'ytmusic_lastfm_match_id_map_{DATE}.tsv'
)
yt_playcounts: Dict[str, Any] = {}
yt_no_lastfm_match: Dict[str, Any] = {}
yt_lastfm_id_map: Dict[str, str] = {}


def match_ytmusic_with_lastfm(
    yt_tracks: pd.DataFrame,
    lastfm_playcount_map: Dict[str, Any],
    existing_id_map: Optional[Dict[str, str]] = None,
    score_thresh: int = 60,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, str]]:
  """Matches YT tracks against Last.fm playcounts using O(1) cache + batch C++ cdist.

  Args:
    yt_tracks: DataFrame of YouTube Music tracks indexed by videoId with
      'fuzzy_id' column.
    lastfm_playcount_map: Mapping of Last.fm fuzzy_id to playcount.
    existing_id_map: Optional pre-existing videoId -> lastfm_fuzzy_id map.
    score_thresh: Minimum fuzzy match score threshold (default 60).

  Returns:
    Tuple of (matched_playcounts, unmatched_tracks, updated_id_map).
  """
  matched_playcounts: Dict[str, Any] = {}
  unmatched_tracks: Dict[str, Any] = {}
  updated_id_map: Dict[str, str] = (
      dict(existing_id_map) if existing_id_map else {}
  )
  lastfm_pool = list(lastfm_playcount_map.keys())

  unmatched_vids = []
  unmatched_queries = []

  for vid, fuzzy_id in zip(yt_tracks.index, yt_tracks['fuzzy_id']):
    lfm_key = updated_id_map.get(vid)
    if lfm_key is not None and lfm_key in lastfm_playcount_map:
      matched_playcounts[vid] = lastfm_playcount_map[lfm_key]
    else:
      unmatched_vids.append(vid)
      unmatched_queries.append(str(fuzzy_id) if pd.notna(fuzzy_id) else '')

  if unmatched_queries:
    print(
        f'Matching {len(unmatched_queries):,} uncached YT tracks against '
        f'{len(lastfm_pool):,} Last.fm tracks via query_fuzz_pool_batch...'
    )
    batch_results = uni.query_fuzz_pool_batch(
        unmatched_queries, lastfm_pool, score_thresh=score_thresh
    )
    for vid, (match, _) in zip(unmatched_vids, batch_results):
      if match is not None and match in lastfm_playcount_map:
        matched_playcounts[vid] = lastfm_playcount_map[match]
        updated_id_map[vid] = match
      else:
        unmatched_tracks[vid] = None

  return matched_playcounts, unmatched_tracks, updated_id_map


def save_tsvs(
    yt_playcounts: Dict[str, Any],
    yt_no_lastfm_match: Dict[str, Any],
    yt_lastfm_id_map: Dict[str, str],
    yt_tracks: pd.DataFrame,
) -> None:
  """Saves Last.fm <-> YTMusic playcount match TSVs and updates marker."""
  yt_no_lastfm_df = pd.DataFrame.from_dict(
      yt_no_lastfm_match, orient='index'
  )
  yt_no_lastfm_df.to_csv(
      yt_no_lastfm_match_f,
      header=True,
      sep='\t',
      index=True,
      encoding='utf-8',
  )

  yt_playcounts_df = pd.DataFrame.from_dict(yt_playcounts, orient='index')
  yt_playcounts_df.columns = ['lastfm_playcount']
  yt_playcounts_df.to_csv(
      yt_playcounts_f, header=True, sep='\t', index=True, encoding='utf-8'
  )
  yt_playcounts_df.to_csv(
      YT_LASTFM_PLACYCOUNT,
      header=True,
      sep='\t',
      index=True,
      encoding='utf-8',
  )
  yt_lastfm_id_df = pd.DataFrame.from_dict(yt_lastfm_id_map, orient='index')
  yt_lastfm_id_df.columns = ['lastfm_fuzzy_id']
  yt_lastfm_id_df.to_csv(
      yt_lastfm_id_map_f, header=True, sep='\t', index=True, encoding='utf-8'
  )
  yt_lastfm_id_df.to_csv(
      YT_LASTFM_MAP, header=True, sep='\t', index=True, encoding='utf-8'
  )
  track_db = pd.concat([yt_tracks, yt_playcounts_df], axis=1)
  track_db = track_db.sort_values(['artist', 'album'])
  if len(track_db) != len(yt_tracks):
    raise ValueError(
        f'Track DB length mismatch: {len(track_db)} != {len(yt_tracks)}'
    )
  if track_db['lastfm_playcount'].sum() <= 0:
    raise ValueError('Total matched Last.fm playcount must be > 0')
  track_db.to_csv(YT_TRACK_DB_OUT, sep='\t', header=True)
  uni.touch_last_run(JOB_NAME)


if __name__ == '__main__':
  if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

  parser = argparse.ArgumentParser(
      description='Match YTMusic tracks with Last.fm playcounts.'
  )
  parser.add_argument(
      '--force',
      '-f',
      action='store_true',
      help='Force run matching ignoring interval threshold',
  )
  args, _ = parser.parse_known_args()

  if not uni.check_should_run(
      JOB_NAME,
      RUN_INTERVAL_DAYS,
      force=args.force,
      fallback_path=YT_LASTFM_PLACYCOUNT,
  ):
    sys.exit(0)

  # INIT
  t1 = time.time()
  print(f'Starting {int(t1)}')
  if LOAD_LAST_MATCHES and os.path.exists(YT_LASTFM_MAP):
    yt_lastfm_id_map = pd.read_csv(
        YT_LASTFM_MAP, sep='\t', index_col=0
    ).to_dict()['lastfm_fuzzy_id']
    print(
        f'Loaded {len(yt_lastfm_id_map)} previous lastfm ytmusic matched'
    )
  lastfm = uni.ingest_lastfm_playcounts(LASTFM_PLAYCOUNTS)
  lastfm_playcount_map = (
      lastfm.drop_duplicates(subset=['fuzzy_id'], keep='first')
      .set_index('fuzzy_id')['playcount']
      .to_dict()
  )
  yt_tracks = uni.ingest_ytmusic_db_assets(
      YT_TRACK_DB_LATEST, save_tsv=True, ytm_db=YT_TRACK_DB_OUT
  )
  print(f'Loaded dbs in {round(time.time() - t1)} seconds...')

  # PROCESS: O(1) cache/exact lookup + vectorized rapidfuzz batch matching
  yt_playcounts, yt_no_lastfm_match, yt_lastfm_id_map = (
      match_ytmusic_with_lastfm(
          yt_tracks,
          lastfm_playcount_map,
          existing_id_map=yt_lastfm_id_map,
          score_thresh=60,
      )
  )

  save_tsvs(yt_playcounts, yt_no_lastfm_match, yt_lastfm_id_map, yt_tracks)

  print('\n--- Last.fm <-> YTMusic Matching Summary ---')
  print(f'Total YTMusic Tracks Evaluated: {len(yt_tracks):,}')
  print(
      f'Matched Playcounts:          {len(yt_playcounts):,} '
      f'({100 * len(yt_playcounts) / max(len(yt_tracks), 1):.1f}%)'
  )
  print(f'Unmatched Tracks:            {len(yt_no_lastfm_match):,}')
  print(f'Total Execution Time:        {(time.time() - t1) / 60:.1f} minutes')
