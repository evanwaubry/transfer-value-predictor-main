from pathlib import Path
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/'app.py'

def test_app_and_empty_filters():
    app=AppTest.from_file(str(APP)).run(timeout=30)
    assert not app.exception
    assert len(app.tabs)==5
    app.sidebar.text_input[0].set_value('no such player xyz').run()
    assert not app.exception
    assert any('No players match' in item.value for item in app.info)


def test_scenario_and_invalid_strategy():
    app=AppTest.from_file(str(APP)).run(timeout=30)
    next(b for b in app.button if b.label=='Estimate this profile').click().run()
    assert not app.exception
    assert any(m.label=='SCENARIO ESTIMATE' for m in app.metric)
    app.sidebar.selectbox[1].select('Forward by season').run()
    assert not app.exception
    assert any('at least two seasons' in item.value for item in app.error)
