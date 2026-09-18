"""Small authenticated client. No credentials in URLs, exports or error messages."""
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import requests
from dotenv import dotenv_values
from config import BASE_URL


class FootballAPIError(ValueError):
    pass


def api_key():
    # Read on demand so saving .env does not require restarting the interpreter.
    return (os.getenv('FOOTBALL_DATA_API_KEY') or dotenv_values(Path(__file__).resolve().parents[1]/'.env').get('FOOTBALL_DATA_API_KEY') or '').strip()


def request(endpoint, params=None):
    key=api_key()
    if not key:
        raise FootballAPIError('No API key configured. Follow the API setup tab and then retry.')
    try:
        response=requests.get(BASE_URL+endpoint,params=params or {},headers={'X-Auth-Token':key},timeout=20)
    except requests.RequestException:
        raise FootballAPIError('Could not reach football-data.org. Check your connection and try again.') from None
    messages={401:'API key rejected. Check your token and account activation.',403:'Your account cannot access this resource or season. Check coverage and subscription permissions.',429:'API rate limit reached. Wait at least a minute before trying again.'}
    if response.status_code in messages:
        raise FootballAPIError(messages[response.status_code])
    if response.status_code>=400:
        raise FootballAPIError(f'Provider returned HTTP {response.status_code}. Try a shorter date range or check provider availability.')
    try:
        payload=response.json()
        if not isinstance(payload,dict):
            raise ValueError()
        return payload
    except ValueError:
        raise FootballAPIError('Provider returned an invalid response. Please retry later.') from None


def recent_matches(start, end):
    """Inclusive UTC calendar dates. Small windows accommodate provider range limits."""
    if start>end or (end-start).days>30:
        raise FootballAPIError('Choose an ordered date range of at most 31 days.')
    rows={}
    cursor=start
    while cursor<=end:
        chunk_end=min(cursor+timedelta(days=6),end)
        # Request through following midnight; local filtering defines our exact bounds.
        data=request('/matches',{'competitions':'PL','dateFrom':cursor.isoformat(),'dateTo':(chunk_end+timedelta(days=1)).isoformat()})
        for match in data.get('matches',[]):
            try:
                kickoff=datetime.fromisoformat(match['utcDate'].replace('Z','+00:00')).astimezone(timezone.utc).date()
            except (KeyError,ValueError,TypeError):
                raise FootballAPIError('A match has no valid kickoff date; retry the provider later.') from None
            competition=match.get('competition',{})
            if start<=kickoff<=end and (competition.get('code')=='PL' or competition.get('id')==2021):
                rows[match['id']]=match
        cursor=chunk_end+timedelta(days=1)
    return sorted(rows.values(),key=lambda m:m['utcDate'],reverse=True)


def current_scorers():
    """Use the provider's current season, not a hardcoded sample year."""
    competition=request('/competitions/PL')
    season=competition.get('currentSeason') or {}
    try:
        year=date.fromisoformat(season['startDate']).year
    except (KeyError,ValueError,TypeError):
        raise FootballAPIError('Provider did not identify a valid current season.') from None
    data=request('/competitions/PL/scorers',{'season':year,'limit':100})
    from src.data_collection import scorer_rows
    return season,scorer_rows(data,year)


def score_label(match):
    score=(match.get('score') or {}).get('fullTime') or {}
    home,away=score.get('home'),score.get('away')
    if home is None or away is None:
        return 'vs'
    return f'{home} – {away}'
