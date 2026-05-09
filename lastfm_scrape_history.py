"""LastFM History Library"""

import os
import time

import pandas as pd
import requests
from requests_toolbelt.threaded import pool

# Generate your own at https://www.last.fm/api/account/create
from auth import LASTFM_API_KEY
from auth import LASTFM_USER_NAME

# https://mathieuhendey.com/2020/10/download-all-your-historical-last.fm-data/#pandas-to-create-a-csv

# Root directory for unified music source outputs
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'music-sources-unified'))

# File paths for saving data
SCROBBLES_TSV = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_scrobbles.tsv')
PLAYCOUNTS_TSV = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_playcounts.tsv')
LASTFM_TOP_ALBUMS = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_top_albums.tsv')


def get_scrobbles(
    endpoint="recenttracks",
    username=LASTFM_USER_NAME,
    api_key=LASTFM_API_KEY,
    limit=200,
    extended=0,
    page=1,
    pages=0,
):
    """Retrieves and processes scrobble data from the Last.fm API.

    Fetches scrobble data for a given user, processes it, and returns a DataFrame.

    Args:
        endpoint: The Last.fm API endpoint. Defaults to "recenttracks".
        username: The Last.fm username.
        api_key: Your Last.fm API key.
        limit: Records per page (max 200). Defaults to 200.
        extended: Retrieve extended results (likes etc.). Defaults to 0 (False).
        page: The first page to retrieve. Defaults to 1.
        pages: Number of pages to fetch after `page` (0 fetches all). Defaults to 0.

    Returns:
        A DataFrame containing the scrobble data.
    """

    base_url = (
        f"https://ws.audioscrobbler.com/2.0/?method=user.get{endpoint}"
        f"&user={username}&api_key={api_key}&limit={limit}&extended={extended}"
        f"&format=json"
    )

    # Determine the total number of pages to fetch
    response = requests.get(f"{base_url}&page={page}").json()
    total_pages = int(response[endpoint]["@attr"]["totalPages"])
    total_pages = min(total_pages, pages) if pages else total_pages

    print(f"Total pages to retrieve: {total_pages}.")

    # Generate URLs for each page to be fetched
    urls = [f"{base_url}&page={
        page_num}" for page_num in range(page, total_pages + 1)]

    # Fetch data concurrently
    p = pool.Pool.from_urls(urls)
    p.join_all()

    # Extract data from responses
    df_data = []
    for response in p.responses():
        if response.ok and endpoint in response.json():
            for track in response.json()[endpoint].get("track", []):
                if "@attr" not in track:
                    df_data.append({
                        "artist": track["artist"]["#text"],
                        "album": track["album"]["#text"],
                        "title": track["name"],
                        "timestamps": int(track["date"]["uts"]),
                    })

    # Create DataFrame from extracted data
    df = pd.DataFrame(df_data)
    df["datetime"] = pd.to_datetime(df["timestamps"], unit="s")
    return df.sort_values("datetime", ascending=True)


def get_time_remaining(pages_remaining: int, time_per_page_ms: int = 115) -> str:
    """Calculates the estimated time remaining for processing.

    Args:
        pages_remaining: The number of pages remaining to process.
        time_per_page_ms: Estimated time to process a single page in milliseconds.

    Returns:
        The estimated time remaining in the format "mm:ss".
    """
    minutes, seconds = divmod(pages_remaining * time_per_page_ms / 1000, 60)
    return f"{int(minutes)}m{int(seconds):02}s"


if __name__ == "__main__":
    # Add path to shared library
    import sys
    sys.path.append(os.path.abspath('../music-sources-unified'))
    import unify_lib as uni

    t0 = time.time()

    # --- Fetch and save all Scrobbles ---
    scrobbles_df = get_scrobbles(page=1, pages=0)  # Default to all Scrobbles
    scrobbles_df.to_csv(SCROBBLES_TSV, sep='\t', index=False, encoding="utf-8")
    print(scrobbles_df.describe())

    # --- Calculate and save Playcounts ---
    sep = "////"
    scrobble_counts = (scrobbles_df.artist + sep + scrobbles_df.album +
                       sep + scrobbles_df.title).value_counts()
    top_entries = pd.DataFrame(
        data=scrobble_counts.index.str.split(sep, n=2).tolist(),
        columns=['artist', 'album', 'title']
    )
    top_entries['playcount'] = scrobble_counts.values
    top_entries.to_csv(PLAYCOUNTS_TSV, sep='\t', index=True)
    print(top_entries.head())

    # --- Load playcounts tsv and analyze top albums ---
    lastfm = uni.ingest_lastfm_playcounts(PLAYCOUNTS_TSV)
    total_playcount = lastfm.groupby('fuzzy_album_id').agg({
        'playcount': ['sum', 'mean'],  # Sum and mean of playcount
        'artist': 'first',             # First artist in each group
        'album': 'first'               # First album in each group
    })
    total_playcount.columns = ['total_playcount',
                               'mean_playcount', 'artist', 'album']
    total_playcount = total_playcount.sort_values(
        by='total_playcount', ascending=False)
    total_playcount.to_csv(LASTFM_TOP_ALBUMS, sep='\t')
    print(f'Top 50 albums:\n{total_playcount.head(50)}')
    print(f'Finished in {(time.time() - t0)/60:0.1f} minutes')
