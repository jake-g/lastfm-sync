"""Unit tests for lastfm_scrape_history.py."""

import os
import sys
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
  sys.path.insert(0, SCRIPT_DIR)

import lastfm_scrape_history as lfm


def _mock_resp(payload: dict, ok: bool = True, status_code: int = 200):
  resp = MagicMock(ok=ok, status_code=status_code)
  resp.json.return_value = payload
  return resp


class TestGetScrobblesReliability(unittest.TestCase):
  """Tests retry, HTTP-200 error handling, dedup, and completeness checks."""

  @patch('lastfm_scrape_history.time.sleep')
  @patch('lastfm_scrape_history.requests.Session')
  def test_retries_http_200_api_error_and_deduplicates(
      self, mock_session_cls, _mock_sleep
  ):
    """Verifies HTTP-200 JSON error=8 is retried and boundary deduped."""
    session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = session
    track = {
        'artist': {'#text': 'Pink Floyd'},
        'album': {'#text': 'The Dark Side of the Moon'},
        'name': 'Brain Damage',
        'date': {'uts': '1700000000'},
    }
    p1 = {
        'recenttracks': {
            '@attr': {'totalPages': '2'},
            'track': [track, {'@attr': {'nowplaying': 'true'}}],
        }
    }
    p2_err = {'error': 8, 'message': 'Operation failed'}
    p2_ok = {'recenttracks': {'@attr': {'totalPages': '2'}, 'track': [track]}}

    def side_effect(url, timeout=20):
      if url.endswith('page=1'):
        return _mock_resp(p1)
      if not getattr(side_effect, 'failed_once', False):
        side_effect.failed_once = True
        return _mock_resp(p2_err)
      return _mock_resp(p2_ok)

    session.get.side_effect = side_effect
    df = lfm.get_scrobbles(username='test', api_key='k', page=1, pages=2)
    self.assertEqual(len(df), 1)
    self.assertEqual(df.iloc[0]['title'], 'Brain Damage')

  @patch.object(lfm, 'SCROBBLES_TSV', '/nonexistent_scrobbles.tsv')
  @patch('lastfm_scrape_history.time.sleep')
  @patch('lastfm_scrape_history.requests.Session')
  def test_raises_on_incomplete_pages(self, mock_session_cls, _mock_sleep):
    """Verifies persistent page failures raise RuntimeError instead of drop."""
    session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = session
    p1 = {'recenttracks': {'@attr': {'totalPages': '2'}, 'track': []}}
    session.get.side_effect = lambda url, timeout=20: (
        _mock_resp(p1)
        if url.endswith('page=1')
        else _mock_resp({}, ok=False, status_code=503)
    )
    with self.assertRaisesRegex(RuntimeError, 'Incomplete Last.fm scrape'):
      lfm.get_scrobbles(username='test', api_key='k', page=1, pages=2)


if __name__ == '__main__':
  unittest.main()
