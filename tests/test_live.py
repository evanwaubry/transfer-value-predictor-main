from datetime import date
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from src import football_api as api


def match(identifier=1,day='2026-09-17',home_score=0,away_score=0):
    return dict(id=identifier,utcDate=day+'T19:00:00Z',competition={'code':'PL'},homeTeam={'name':'Home FC'},awayTeam={'name':'Away FC'},status='FINISHED',score={'fullTime':{'home':home_score,'away':away_score}},matchday=5)


def test_scores_preserve_zero_and_unknown():
    assert api.score_label(match())=='0 – 0'
    assert api.score_label(match(home_score=None,away_score=None))=='vs'


def test_date_filter_dedupe_and_query(monkeypatch):
    queries=[]
    def response(endpoint,params):
        queries.append((endpoint,params))
        return {'matches':[match(),match(),match(2,'2026-09-18'),match(3,'2026-09-10')]}
    monkeypatch.setattr(api,'request',response)
    rows=api.recent_matches(date(2026,9,11),date(2026,9,17))
    assert len(rows)==1
    assert queries[0][1]=={'competitions':'PL','dateFrom':'2026-09-11','dateTo':'2026-09-18'}
    with pytest.raises(api.FootballAPIError):api.recent_matches(date(2026,9,17),date(2026,9,11))


def test_current_season_from_api(monkeypatch):
    queries=[]
    def response(endpoint,params=None):
        queries.append((endpoint,params))
        return {'currentSeason':{'startDate':'2027-08-01','endDate':'2028-05-30'}} if endpoint.endswith('/PL') else {'scorers':[]}
    monkeypatch.setattr(api,'request',response)
    season,rows=api.current_scorers()
    assert queries[1][1]=={'season':2027,'limit':100}


@pytest.mark.parametrize('status',[401,403,429,500])
def test_safe_errors(monkeypatch,status):
    from types import SimpleNamespace
    monkeypatch.setattr(api,'api_key',lambda:'test-secret')
    monkeypatch.setattr(api.requests,'get',lambda *a,**k:SimpleNamespace(status_code=status))
    with pytest.raises(api.FootballAPIError) as exc:api.request('/matches')
    assert 'test-secret' not in str(exc.value)


def test_live_ui_offline_and_loaded(monkeypatch):
    from src import live_ui
    monkeypatch.setattr(api,'api_key',lambda:'')
    monkeypatch.setattr(live_ui,'api_key',lambda:'')
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    app.sidebar.radio[0].set_value('Live football').run()
    assert not app.exception
    assert [t.label for t in app.tabs]==['Recent matches','Current-season stats','API setup']
    monkeypatch.setattr(live_ui,'recent_matches',lambda a,b:[match()])
    next(b for b in app.button if b.label=='Load / refresh matches').click().run()
    assert not app.exception
    assert any('Home FC' in m.value for m in app.markdown)
    assert any(m.value=='0 – 0' or '0 – 0' in m.value for m in app.markdown)
