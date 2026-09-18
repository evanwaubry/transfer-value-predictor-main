from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.model import evaluate, evaluation_splits
from src.data_processing import validate_dataset, merge_with_transfer_values

@pytest.fixture
def data():
    return pd.read_csv(Path(__file__).resolve().parents[1]/'data/sample_dataset.csv')


def test_group_exclusion_and_evaluation(data):
    extra=data.copy(); extra['season']+=1
    df,_=validate_dataset(pd.concat([data,extra],ignore_index=True))
    for train,test in evaluation_splits(df):
        assert set(df.iloc[train]._player_group).isdisjoint(df.iloc[test]._player_group)
    _,metrics,result=evaluate(df)
    assert result.predicted_value_eur.notna().all()
    assert (result.predicted_value_eur>=0).all()
    assert metrics['mae_eur']==pytest.approx(np.mean(abs(result.predicted_value_eur-df.transfer_value_eur)))


def test_forward_never_trains_on_future(data):
    extra=data.copy(); extra['season']+=1
    df,_=validate_dataset(pd.concat([data,extra],ignore_index=True))
    for train,test in evaluation_splits(df,'Forward by season'):
        assert df.iloc[train].season.max()<df.iloc[test].season.min()
    _,metrics,result=evaluate(df,'Forward by season')
    assert result.loc[result.season==2024,'predicted_value_eur'].isna().all()
    assert metrics['n_test']==len(data)

@pytest.mark.parametrize('column,value',[('age',np.nan),('goals',-1),('assists',np.inf),('transfer_value_eur',0),('appearances',3.5),('position','Unknown')])
def test_invalid_values_rejected(data,column,value):
    data.loc[0,column]=value
    with pytest.raises(ValueError): validate_dataset(data)


def test_duplicate_rejected(data):
    with pytest.raises(ValueError,match='Duplicate'): validate_dataset(pd.concat([data,data.iloc[[0]]]))


def test_join_is_exact_and_season_specific(data):
    stats=data.drop(columns='transfer_value_eur')
    values=data[['name','season','transfer_value_eur']].copy()
    merged=merge_with_transfer_values(stats,values)
    assert len(merged)==len(data)
    values.loc[0,'name']='Erling Haland'
    with pytest.raises(ValueError,match='Unmatched'): merge_with_transfer_values(stats,values)
    with pytest.raises(ValueError,match='season'): merge_with_transfer_values(stats,values.drop(columns='season'))


def test_snapshot_leakage(data):
    data['stats_as_of']='2025-06-01'; data['valuation_date']='2025-01-01'
    with pytest.raises(ValueError,match='Dates'): validate_dataset(data)


def test_target_not_used_as_feature(data):
    from src.model import build_pipeline, FEATURES
    model=build_pipeline().fit(data,data.transfer_value_eur)
    changed=data.copy(); changed.transfer_value_eur=1
    np.testing.assert_allclose(model.predict(data),model.predict(changed))
