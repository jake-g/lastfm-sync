import time
import pandas as pd
from shutil import copyfile
import unify_lib as uni

# TODO: have option to only update tracks with missing playcount
#   and redo all like every X months)
LOG_EVERY = 500
DATE = time.strftime('%m-%d-%Y')

LASTFM_PLAYCOUNTS = './tsvs/lastfm_playcounts.tsv'
YT_TRACK_DB_LATEST = '../ytmusic/playlists/_tracks_db.tsv'
YT_TRACK_DB_OUT = './tsvs/ytmusic_all_database.tsv'
YTMUSIC_MATCHED = './db_assets/ytmusic_tracks_db.tsv'
YT_LASTFM_MAP = '../ytmusic/playlists/_ytmusic_lastfm_match_id_map.tsv'
YT_LASTFM_PLACYCOUNT = '../ytmusic/playlists/_ytmusic_lastfm_playcount.tsv'

LOAD_LAST_MATCHES = True


YTB_CP_COLS = ['title', 'album', 'likeStatus', 'duration', 'artistId',
               'albumId', 'playlists', 'averageRating', 'viewCount',
               'albumArtist', 'albumYear', 'albumTrackCount',
               'albumDuration', 'albumType', 'fuzzy_album_id', 'fuzzy_id']
copyfile(YT_TRACK_DB_LATEST, YTMUSIC_MATCHED)

yt_no_lastfm_match_f = f'./logs/ytmusic_no_lastfm_match_{DATE}.tsv'
yt_playcounts_f = f'./logs/ytmusic_lastfm_playcounts_{DATE}.tsv'
yt_lastfm_id_map_f = f'./logs/ytmusic_lastfm_match_id_map_{DATE}.tsv'
yt_playcounts = {}
yt_no_lastfm_match = {}
yt_lastfm_id_map = {}  # key is ytmusic fuzzy id, value last fm fuzz id


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


if __name__ == "__main__":
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
        YTMUSIC_MATCHED, save_tsv=True, ytm_db=YT_TRACK_DB_OUT)
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
                  f"expected total duration:"
                  f"{round(avg_process_time_s*n/3600.0,1)} hours",
                  f"\n  Matched {round(100*len(yt_playcounts)/i,1)}%,",
                  f"{len(yt_playcounts)} playcounts,",
                  f"{len(yt_no_lastfm_match)} unmatched...")
            save_tsvs(yt_playcounts, yt_no_lastfm_match,
                      yt_lastfm_id_map, yt_tracks)  # backup incase stop

    save_tsvs(yt_playcounts, yt_no_lastfm_match, yt_lastfm_id_map, yt_tracks)
