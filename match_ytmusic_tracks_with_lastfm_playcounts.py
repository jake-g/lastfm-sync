import argparse
import os
from shutil import copyfile
import sys
import time

import pandas as pd

# Root directory for unified music source outputs
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'music-sources-unified'))

# Run Interval Threshold (90 days = 3 months default)
RUN_INTERVAL_DAYS = 90
LAST_RUN_MARKER = os.path.join(OUTPUT_DIR, 'tsvs', '.last_ytmusic_lastfm_match_run')

LOG_EVERY = 500
DATE = time.strftime('%m-%d-%Y')

LASTFM_PLAYCOUNTS = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_playcounts.tsv')
YT_TRACK_DB_LATEST = os.path.join(OUTPUT_DIR, '../ytmusic/playlists/_tracks_db.tsv')
YT_TRACK_DB_OUT = os.path.join(OUTPUT_DIR, 'tsvs', 'ytmusic_all_database.tsv')
YT_LASTFM_MAP = os.path.join(OUTPUT_DIR, '../ytmusic/playlists/_ytmusic_lastfm_match_id_map.tsv')
YT_LASTFM_PLACYCOUNT = os.path.join(OUTPUT_DIR, '../ytmusic/playlists/_ytmusic_lastfm_playcount.tsv')

LOAD_LAST_MATCHES = True

YTB_CP_COLS = ['title', 'album', 'likeStatus', 'duration', 'artistId',
               'albumId', 'playlists', 'averageRating', 'viewCount',
               'albumArtist', 'albumYear', 'albumTrackCount',
               'albumDuration', 'albumType', 'fuzzy_album_id', 'fuzzy_id']

yt_no_lastfm_match_f = os.path.join(OUTPUT_DIR, 'logs', f'ytmusic_no_lastfm_match_{DATE}.tsv')
yt_playcounts_f = os.path.join(OUTPUT_DIR, 'logs', f'ytmusic_lastfm_playcounts_{DATE}.tsv')
yt_lastfm_id_map_f = os.path.join(OUTPUT_DIR, 'logs', f'ytmusic_lastfm_match_id_map_{DATE}.tsv')
yt_playcounts = {}
yt_no_lastfm_match = {}
yt_lastfm_id_map = {}  # key is ytmusic fuzzy id, value last fm fuzz id


def check_should_run(force: bool = False) -> bool:
  """Checks if script should run based on RUN_INTERVAL_DAYS threshold."""
  if force:
    print("Force flag set: Running Last.fm playcount matching ignoring interval threshold.")
    return True

  target_file = LAST_RUN_MARKER if os.path.exists(LAST_RUN_MARKER) else (YT_LASTFM_PLACYCOUNT if os.path.exists(YT_LASTFM_PLACYCOUNT) else None)

  if target_file and os.path.exists(target_file):
    mtime = os.path.getmtime(target_file)
    elapsed_days = (time.time() - mtime) / (24 * 3600)
    if elapsed_days < RUN_INTERVAL_DAYS:
      print(f"\nSkipping Last.fm <-> YTMusic playcount matching:")
      print(f"  -> Last run was {elapsed_days:.1f} days ago (Interval threshold: {RUN_INTERVAL_DAYS} days).")
      print(f"  -> Use --force to override and run immediately.\n")
      return False
  return True


def touch_last_run_marker():
  """Updates the marker file with current timestamp."""
  try:
    os.makedirs(os.path.dirname(LAST_RUN_MARKER), exist_ok=True)
    with open(LAST_RUN_MARKER, 'w', encoding='utf-8') as f:
      f.write(f"last_run={time.time()}\nlast_run_date={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
  except Exception as e:
    print(f"Warning writing last run marker: {e}")


def save_tsvs(yt_playcounts, yt_no_lastfm_match, yt_lastfm_id_map, yt_tracks):
    yt_no_lastfm_match = yt_no_lastfm_match.copy()
    yt_no_lastfm_match = pd.DataFrame.from_dict(
        yt_no_lastfm_match, orient='index')
    yt_no_lastfm_match.to_csv(yt_no_lastfm_match_f,
                              header=True, sep='\t', index=True, encoding='utf-8')

    yt_playcounts = yt_playcounts.copy()
    yt_playcounts = pd.DataFrame.from_dict(yt_playcounts, orient='index')
    yt_playcounts.columns = ['lastfm_playcount']
    yt_playcounts.to_csv(yt_playcounts_f,
                         header=True, sep='\t', index=True, encoding='utf-8')
    yt_playcounts.to_csv(YT_LASTFM_PLACYCOUNT,
                         header=True, sep='\t', index=True, encoding='utf-8')
    yt_lastfm_id_map = yt_lastfm_id_map.copy()
    yt_lastfm_id_map = pd.DataFrame.from_dict(yt_lastfm_id_map, orient='index')
    yt_lastfm_id_map.columns = ['lastfm_fuzzy_id']
    yt_lastfm_id_map.to_csv(yt_lastfm_id_map_f,
                            header=True, sep='\t', index=True, encoding='utf-8')
    yt_lastfm_id_map.to_csv(YT_LASTFM_MAP,
                            header=True, sep='\t', index=True, encoding='utf-8')
    track_db = pd.concat([yt_tracks, yt_playcounts], axis=1)
    track_db = track_db.sort_values(['artist', 'album'])
    assert len(track_db) == len(yt_tracks)
    assert track_db['lastfm_playcount'].sum() > 0
    track_db.to_csv(YT_TRACK_DB_OUT, sep='\t', header=True)
    touch_last_run_marker()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Match YTMusic tracks with Last.fm playcounts.")
    parser.add_argument('--force', '-f', action='store_true', help="Force run matching ignoring interval threshold")
    args, _ = parser.parse_known_args()

    if not check_should_run(force=args.force):
        sys.exit(0)

    # Add path to shared library
    module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'music-sources-unified'))
    if module_path not in sys.path:
        sys.path.append(module_path)
    import unify_lib as uni

    # INIT
    t1 = time.time()
    print(f'Starting {int(t1)}')
    if LOAD_LAST_MATCHES:
        yt_lastfm_id_map = pd.read_csv(
            YT_LASTFM_MAP,  sep='\t', index_col=0
        ).to_dict()['lastfm_fuzzy_id']
        print(f'Loaded {len(yt_lastfm_id_map)}',
              'previous lastfm ytmusic matched')
    lastfm = uni.ingest_lastfm_playcounts(LASTFM_PLAYCOUNTS)
    lastfm_fuzzy_set = frozenset(lastfm['fuzzy_id'])
    yt_tracks = uni.ingest_ytmusic_db_assets(
        YT_TRACK_DB_LATEST, save_tsv=True, ytm_db=YT_TRACK_DB_OUT)
    print(f'Loaded dbs in {round(time.time() - t1)} seconds...')

    # PROCESS
    t0 = time.time()
    for i, (vid, yt_track) in enumerate(yt_tracks.iterrows()):
        query_lastfm = True
        if vid in yt_lastfm_id_map:
            try:
                lfm_key = yt_lastfm_id_map[vid]
                if lfm_key in lastfm_fuzzy_set:
                    query_lastfm = False
                    lastfm_res = lastfm.loc[
                        lastfm['fuzzy_id'] == lfm_key].iloc[0]
                    if not len(lastfm_res):
                        query_lastfm = True
            except Exception as e:
                query_lastfm = True
                print(e)

        if query_lastfm:
            lastfm_res = uni.query_lastfm_for_yt_tracks(
                yt_track, lastfm, score_thresh=60)
        if len(lastfm_res):
            yt_playcounts[vid] = lastfm_res['playcount']
            yt_lastfm_id_map[vid] = lastfm_res['fuzzy_id']
        else:
            yt_no_lastfm_match[vid] = None

        if (i+1) % LOG_EVERY == 0:
            elapsed_time = float(time.time() - t0)
            avg_process_time_s = round(elapsed_time/i, 1)
            n = len(yt_tracks)
            print(f"Processed {round(100*i/n,1)}%, {i+1} of {n} tracks in",
                  f"{round(elapsed_time/60.0)} minutes",
                  f"\n  Process rate: {avg_process_time_s} seconds per track,",
                  f"expected total duration:",
                  f"{round(avg_process_time_s*n/3600.0,1)} hours",
                  f"\n  Matched {round(100*len(yt_playcounts)/i,1)}%,",
                  f"{len(yt_playcounts)} playcounts,",
                  f"{len(yt_no_lastfm_match)} unmatched...")
            save_tsvs(yt_playcounts, yt_no_lastfm_match,
                      yt_lastfm_id_map, yt_tracks)  # backup incase stop

    save_tsvs(yt_playcounts, yt_no_lastfm_match, yt_lastfm_id_map, yt_tracks)

    print("\n--- Last.fm <-> YTMusic Matching Summary ---")
    print(f"Total YTMusic Tracks Evaluated: {len(yt_tracks):,}")
    print(f"Matched Playcounts:          {len(yt_playcounts):,} ({100*len(yt_playcounts)/max(len(yt_tracks),1):.1f}%)")
    print(f"Unmatched Tracks:            {len(yt_no_lastfm_match):,}")
    print(f"Total Execution Time:        {(time.time() - t1)/60:.1f} minutes")
