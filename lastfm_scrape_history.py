"""Last.fm history scraping and playcount aggregation module."""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from auth import LASTFM_API_KEY, LASTFM_USER_NAME

# Root directory for unified music source outputs
OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'music-sources-unified')
)

# File paths for saving data
SCROBBLES_TSV = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_scrobbles.tsv')
PLAYCOUNTS_TSV = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_playcounts.tsv')
LASTFM_TOP_ALBUMS = os.path.join(OUTPUT_DIR, 'tsvs', 'lastfm_top_albums.tsv')
SCROBBLE_SEP = '////'


def get_scrobbles(
    endpoint: str = 'recenttracks',
    username: str = LASTFM_USER_NAME,
    api_key: str = LASTFM_API_KEY,
    limit: int = 200,
    extended: int = 0,
    page: int = 1,
    pages: int = 0,
) -> pd.DataFrame:
  """Retrieves and processes scrobble data from the Last.fm API.

  Fetches scrobble data for a given user, processes it, and returns a DataFrame.

  Args:
      endpoint: The Last.fm API endpoint. Defaults to 'recenttracks'.
      username: The Last.fm username.
      api_key: Your Last.fm API key.
      limit: Records per page (max 200). Defaults to 200.
      extended: Retrieve extended results (likes etc.). Defaults to 0 (False).
      page: The first page to retrieve. Defaults to 1.
      pages: Number of pages to fetch after `page` (0 fetches all). Defaults to
        0.

  Returns:
      A DataFrame containing the scrobble data.
  """
  base_url = (
      f'https://ws.audioscrobbler.com/2.0/?method=user.get{endpoint}'
      f'&user={username}&api_key={api_key}&limit={limit}&extended={extended}'
      f'&format=json'
  )

  try:
    response = requests.get(f'{base_url}&page={page}', timeout=10).json()
    total_pages = int(response[endpoint]['@attr']['totalPages'])
    total_pages = min(total_pages, pages) if pages else total_pages

    print(f'Total pages to retrieve: {total_pages}.')

    urls = [
        f'{base_url}&page={page_num}'
        for page_num in range(page, total_pages + 1)
    ]

    def fetch_url(url: str):
      try:
        resp = requests.get(url, timeout=15)
        return resp if resp.ok else None
      except Exception:
        return None

    print(f'Fetching {len(urls)} pages concurrently with ThreadPoolExecutor...')
    responses = []
    with ThreadPoolExecutor(max_workers=20) as executor:
      future_to_url = {executor.submit(fetch_url, url): url for url in urls}
      for future in as_completed(future_to_url):
        res = future.result()
        if res:
          responses.append(res)

    df_data = []
    for response in responses:
      res_json = (
          response.json() if hasattr(response, 'json') else response.json
      )
      if hasattr(response, 'ok') and response.ok and endpoint in res_json:
        for track in res_json[endpoint].get('track', []):
          if '@attr' not in track:
            df_data.append({
                'artist': track['artist']['#text'],
                'album': track['album']['#text'],
                'title': track['name'],
                'timestamps': int(track['date']['uts']),
            })

    df = pd.DataFrame(df_data)
    if not df.empty:
      df['datetime'] = pd.to_datetime(df['timestamps'], unit='s')
      return df.sort_values('datetime', ascending=True)
    return df
  except Exception as e:
    print(f'Warning: Last.fm API fetch failed ({e}).')
    if os.path.exists(SCROBBLES_TSV):
      print(f'Falling back to existing local scrobbles file: {SCROBBLES_TSV}')
      df = pd.read_csv(SCROBBLES_TSV, sep='\t')
      if 'timestamps' in df.columns and 'datetime' not in df.columns:
        df['datetime'] = pd.to_datetime(df['timestamps'], unit='s')
      return df
    raise


def get_time_remaining(
    pages_remaining: int, time_per_page_ms: int = 115
) -> str:
  """Calculates the estimated time remaining for processing.

  Args:
      pages_remaining: The number of pages remaining to process.
      time_per_page_ms: Estimated time to process a single page in milliseconds.

  Returns:
      The estimated time remaining in the format 'mm:ss'.
  """
  minutes, seconds = divmod(pages_remaining * time_per_page_ms / 1000, 60)
  return f'{int(minutes)}m{int(seconds):02}s'


def compute_scrobble_playcounts(scrobbles_df: pd.DataFrame) -> pd.DataFrame:
  """Aggregates scrobble rows into per-track playcount counts."""
  scrobble_counts = (
      scrobbles_df.artist.fillna('')
      + SCROBBLE_SEP
      + scrobbles_df.album.fillna('')
      + SCROBBLE_SEP
      + scrobbles_df.title.fillna('')
  ).value_counts()
  top_entries = pd.DataFrame(
      data=scrobble_counts.index.str.split(SCROBBLE_SEP, n=2).tolist(),
      columns=['artist', 'album', 'title'],
  )
  top_entries['playcount'] = scrobble_counts.values
  return top_entries


def compute_top_albums(lastfm_df: pd.DataFrame) -> pd.DataFrame:
  """Aggregates Last.fm track playcounts by fuzzy_album_id."""
  total_playcount = lastfm_df.groupby('fuzzy_album_id').agg({
      'playcount': ['sum', 'mean'],
      'artist': 'first',
      'album': 'first',
  })
  total_playcount.columns = [
      'total_playcount',
      'mean_playcount',
      'artist',
      'album',
  ]
  return total_playcount.sort_values(by='total_playcount', ascending=False)


if __name__ == '__main__':
  if OUTPUT_DIR not in sys.path:
    sys.path.append(OUTPUT_DIR)

  # isort: split
  import unify_lib as uni

  pd.set_option('display.max_columns', None)
  pd.set_option('display.width', 1000)
  pd.set_option('display.max_rows', 200)

  t0 = time.time()

  scrobbles_df = get_scrobbles(page=1, pages=0)
  scrobbles_df.to_csv(SCROBBLES_TSV, sep='\t', index=False, encoding='utf-8')

  print('\n--- Scrobbles Overview ---')
  print(f'Total Scrobbles: {len(scrobbles_df):,}')
  if not scrobbles_df.empty and 'datetime' in scrobbles_df:
    print(
        f"Date Range:      {scrobbles_df['datetime'].min()} to "
        f"{scrobbles_df['datetime'].max()}"
    )
  print(f"Unique Artists:  {scrobbles_df['artist'].nunique():,}")
  print(f"Unique Albums:   {scrobbles_df['album'].nunique():,}")
  print(f"Unique Tracks:   {scrobbles_df['title'].nunique():,}")

  print('\n--- Top 50 Artists ---')
  top_artists = scrobbles_df['artist'].value_counts().head(50).reset_index()
  top_artists.columns = ['artist', 'scrobbles']
  print(top_artists.to_string(index=False))

  top_entries = compute_scrobble_playcounts(scrobbles_df)
  top_entries.to_csv(PLAYCOUNTS_TSV, sep='\t', index=True)

  print('\n--- Top 50 Most Scrobbled Tracks ---')
  print(top_entries.head(50).to_string(index=False))

  lastfm = uni.ingest_lastfm_playcounts(PLAYCOUNTS_TSV)
  total_playcount = compute_top_albums(lastfm)
  total_playcount.to_csv(LASTFM_TOP_ALBUMS, sep='\t')

  print('\n--- Top 50 Most Scrobbled Albums ---')
  print(
      total_playcount[
          ['artist', 'album', 'total_playcount', 'mean_playcount']
      ]
      .head(50)
      .to_string(index=False)
  )

  print(f'\nJob finished in {(time.time() - t0) / 60:0.1f} minutes.')
