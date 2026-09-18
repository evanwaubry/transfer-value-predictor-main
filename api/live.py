"""Vercel serverless function: proxy football-data.org so the API token never
reaches the browser. Reads FOOTBALL_DATA_API_KEY from Vercel's environment
variables (Project Settings -> Environment Variables), not from a .env file.

GET /api/live?action=test
GET /api/live?action=matches&start=YYYY-MM-DD&end=YYYY-MM-DD
GET /api/live?action=scorers
"""
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import json
import os

import requests

BASE_URL = 'https://api.football-data.org/v4'


class APIError(Exception):
    pass


def api_key():
    return (os.environ.get('FOOTBALL_DATA_API_KEY') or '').strip()


def fd_request(endpoint, params=None):
    key = api_key()
    if not key:
        raise APIError('No API key configured. Add FOOTBALL_DATA_API_KEY in your Vercel '
                        'project\u2019s Environment Variables, then redeploy.')
    try:
        response = requests.get(BASE_URL + endpoint, params=params or {},
                                 headers={'X-Auth-Token': key}, timeout=20)
    except requests.RequestException:
        raise APIError('Could not reach football-data.org. Check connectivity and try again.') from None
    messages = {
        401: 'API key rejected. Check your token and account activation.',
        403: 'Your account cannot access this resource or season. Check coverage and subscription permissions.',
        429: 'API rate limit reached. Wait at least a minute before trying again.',
    }
    if response.status_code in messages:
        raise APIError(messages[response.status_code])
    if response.status_code >= 400:
        raise APIError(f'Provider returned HTTP {response.status_code}. Try a shorter date range or check provider availability.')
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except ValueError:
        raise APIError('Provider returned an invalid response. Please retry later.') from None


def score_label(match):
    score = (match.get('score') or {}).get('fullTime') or {}
    home, away = score.get('home'), score.get('away')
    return 'vs' if home is None or away is None else f'{home} \u2013 {away}'


def recent_matches(start, end):
    if start > end or (end - start).days > 30:
        raise APIError('Choose an ordered date range of at most 31 days.')
    rows = {}
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=6), end)
        data = fd_request('/matches', {
            'competitions': 'PL',
            'dateFrom': cursor.isoformat(),
            'dateTo': (chunk_end + timedelta(days=1)).isoformat(),
        })
        for match in data.get('matches', []):
            try:
                kickoff = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00')).astimezone(timezone.utc).date()
            except (KeyError, ValueError, TypeError):
                raise APIError('A match has no valid kickoff date; retry the provider later.') from None
            competition = match.get('competition', {})
            if start <= kickoff <= end and (competition.get('code') == 'PL' or competition.get('id') == 2021):
                rows[match['id']] = match
        cursor = chunk_end + timedelta(days=1)
    return sorted(rows.values(), key=lambda m: m['utcDate'], reverse=True)


def compute_age(dob_str, as_of_year):
    if not dob_str:
        return None
    try:
        dob = datetime.strptime(dob_str[:10], '%Y-%m-%d').date()
    except ValueError:
        return None
    return round((date(int(as_of_year), 8, 1) - dob).days / 365.25, 1)


def current_scorers():
    competition = fd_request('/competitions/PL')
    season = competition.get('currentSeason') or {}
    try:
        year = date.fromisoformat(season['startDate']).year
    except (KeyError, ValueError, TypeError):
        raise APIError('Provider did not identify a valid current season.') from None
    data = fd_request('/competitions/PL/scorers', {'season': year, 'limit': 100})
    rows = []
    for entry in data.get('scorers', []):
        player = entry['player']
        rows.append({
            'player_id': player['id'],
            'name': player['name'],
            'position': player.get('position') or 'Unknown',
            'team': entry['team']['name'],
            'season': year,
            'appearances': entry.get('playedMatches'),
            'goals': entry.get('goals'),
            'assists': entry.get('assists'),
            'penalties': entry.get('penalties'),
            'age': compute_age(player.get('dateOfBirth'), year),
        })
    return season, rows


class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        action = (query.get('action') or [''])[0]
        try:
            if action == 'test':
                payload = fd_request('/competitions/PL')
                season = payload.get('currentSeason') or {}
                self._send(200, {
                    'ok': True,
                    'name': payload.get('name', 'Premier League'),
                    'season_start': season.get('startDate'),
                    'season_end': season.get('endDate'),
                })
            elif action == 'matches':
                start = date.fromisoformat((query.get('start') or [''])[0])
                end = date.fromisoformat((query.get('end') or [''])[0])
                rows = recent_matches(start, end)
                out = [{
                    'match_id': m['id'],
                    'utc_date': m['utcDate'],
                    'home': (m.get('homeTeam') or {}).get('name', 'Unknown'),
                    'away': (m.get('awayTeam') or {}).get('name', 'Unknown'),
                    'score': score_label(m),
                    'status': m.get('status'),
                    'matchday': m.get('matchday'),
                    'half_time': (m.get('score') or {}).get('halfTime'),
                    'venue': m.get('venue'),
                    'referees': [r.get('name') for r in m.get('referees', []) if r.get('name')],
                    'last_updated': m.get('lastUpdated'),
                } for m in rows]
                self._send(200, {'ok': True, 'rows': out})
            elif action == 'scorers':
                season, rows = current_scorers()
                self._send(200, {'ok': True, 'season': season, 'rows': rows})
            else:
                self._send(400, {'ok': False, 'error': 'Unknown or missing action parameter.'})
        except APIError as exc:
            self._send(400, {'ok': False, 'error': str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {'ok': False, 'error': f'Unexpected server error: {exc}'})
