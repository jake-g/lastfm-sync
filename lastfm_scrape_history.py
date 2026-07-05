"""LastFM History Library"""

from concurrent.futures import as_completed
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import time

from auth import LASTFM_API_KEY
from auth import LASTFM_USER_NAME
import pandas as pd
import requests

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

    try:
        # Determine the total number of pages to fetch
        response = requests.get(f"{base_url}&page={page}", timeout=10).json()
        total_pages = int(response[endpoint]["@attr"]["totalPages"])
        total_pages = min(total_pages, pages) if pages else total_pages

        print(f"Total pages to retrieve: {total_pages}.")

        # Generate URLs for each page to be fetched
        urls = [f"{base_url}&page={page_num}" for page_num in range(page, total_pages + 1)]

        # Fetch data concurrently using ThreadPoolExecutor
        def fetch_url(url):
            try:
                resp = requests.get(url, timeout=15)
                return resp if resp.ok else None
            except Exception:
                return None

        print(f"Fetching {len(urls)} pages concurrently with ThreadPoolExecutor...")
        responses = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_url = {executor.submit(fetch_url, url): url for url in urls}
            for future in as_completed(future_to_url):
                res = future.result()
                if res:
                    responses.append(res)

        # Extract data from responses
        df_data = []
        for response in responses:
            res_json = response.json() if hasattr(response, 'json') else response.json
            if hasattr(response, 'ok') and response.ok and endpoint in res_json:
                for track in res_json[endpoint].get("track", []):
                    if "@attr" not in track:
                        df_data.append({
                            "artist": track["artist"]["#text"],
                            "album": track["album"]["#text"],
                            "title": track["name"],
                            "timestamps": int(track["date"]["uts"]),
                        })

        # Create DataFrame from extracted data
        df = pd.DataFrame(df_data)
        if not df.empty:
            df["datetime"] = pd.to_datetime(df["timestamps"], unit="s")
            return df.sort_values("datetime", ascending=True)
        return df
    except Exception as e:
        print(f"Warning: Last.fm API fetch failed ({e}).")
        if os.path.exists(SCROBBLES_TSV):
            print(f"Falling back to existing local scrobbles file: {SCROBBLES_TSV}")
            df = pd.read_csv(SCROBBLES_TSV, sep='\t')
            if 'timestamps' in df.columns and 'datetime' not in df.columns:
                df["datetime"] = pd.to_datetime(df["timestamps"], unit="s")
            return df
        raise


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

    # Configure pandas formatting to prevent truncation in log files
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    pd.set_option('display.max_rows', 200)

    t0 = time.time()

    # --- Fetch and save all Scrobbles ---
    scrobbles_df = get_scrobbles(page=1, pages=0)  # Default to all Scrobbles
    scrobbles_df.to_csv(SCROBBLES_TSV, sep='\t', index=False, encoding="utf-8")

    print("\n--- Scrobbles Overview ---")
    print(f"Total Scrobbles: {len(scrobbles_df):,}")
    if not scrobbles_df.empty and 'datetime' in scrobbles_df:
        print(f"Date Range:      {scrobbles_df['datetime'].min()} to {scrobbles_df['datetime'].max()}")
    print(f"Unique Artists:  {scrobbles_df['artist'].nunique():,}")
    print(f"Unique Albums:   {scrobbles_df['album'].nunique():,}")
    print(f"Unique Tracks:   {scrobbles_df['title'].nunique():,}")

    print("\n--- Top 50 Artists ---")
    top_artists = scrobbles_df['artist'].value_counts().head(50).reset_index()
    top_artists.columns = ['artist', 'scrobbles']
    print(top_artists.to_string(index=False))

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

    print("\n--- Top 50 Most Scrobbled Tracks ---")
    print(top_entries.head(50).to_string(index=False))

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

    print("\n--- Top 50 Most Scrobbled Albums ---")
    print(total_playcount[['artist', 'album', 'total_playcount', 'mean_playcount']].head(50).to_string(index=False))

    print(f'\nJob finished in {(time.time() - t0)/60:0.1f} minutes.')
