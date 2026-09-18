"""Leakage-aware evaluation of a fixed regularized model; no claimed fair price."""
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from src.data_processing import validate_dataset

NUMERIC_FEATURES = ['goals', 'assists', 'appearances', 'age']
CATEGORICAL_FEATURES = ['position']
TARGET = 'transfer_value_eur'
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_pipeline():
    return Pipeline([
        ('preprocess', ColumnTransformer([
            ('numeric', StandardScaler(), NUMERIC_FEATURES),
            ('position', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL_FEATURES),
        ], remainder='drop')),
        ('model', Ridge(alpha=10.0)),
    ])


def predict_nonnegative(model, frame):
    return np.maximum(0, model.predict(frame[FEATURES]))


def evaluation_splits(df, strategy='Player-held-out'):
    if strategy == 'Forward by season':
        seasons = sorted(df.season.unique())
        if len(seasons) < 2:
            raise ValueError('Forward evaluation needs at least two seasons.')
        return [(np.flatnonzero(df.season < s), np.flatnonzero(df.season == s)) for s in seasons[1:]]
    if strategy != 'Player-held-out':
        raise ValueError('Unknown evaluation strategy.')
    return list(GroupKFold(n_splits=min(5, df._player_group.nunique())).split(df, groups=df._player_group))


def evaluate(df, strategy='Player-held-out'):
    df, warnings = validate_dataset(df)
    predictions = np.full(len(df), np.nan)
    baseline = np.full(len(df), np.nan)
    fold_ids = np.full(len(df), -1)
    folds = []
    for fold, (a, b) in enumerate(evaluation_splits(df, strategy), 1):
        training, testing = df.iloc[a], df.iloc[b]
        model = build_pipeline().fit(training[FEATURES], training[TARGET])
        predictions[b] = predict_nonnegative(model, testing)
        medians = training.groupby('position')[TARGET].median()
        baseline[b] = testing.position.map(medians).fillna(training[TARGET].median())
        fold_ids[b] = fold
        folds.append({'fold': fold, 'train_rows': len(a), 'test_rows': len(b), 'mae_eur': mean_absolute_error(testing[TARGET], predictions[b])})
    valid = np.isfinite(predictions)
    y, p = df.loc[valid, TARGET], predictions[valid]
    metrics = {'mae_eur': float(mean_absolute_error(y, p)), 'rmse_eur': float(np.sqrt(mean_squared_error(y, p))),
               'r2': float(r2_score(y, p)) if len(y) > 1 and y.nunique() > 1 else None,
               'baseline_mae_eur': float(mean_absolute_error(y, baseline[valid])),
               'n_test': int(valid.sum()), 'n_train': folds[-1]['train_rows'], 'strategy': strategy,
               'folds': folds, 'warnings': warnings}
    result = df.copy()
    result['predicted_value_eur'] = predictions
    result['baseline_value_eur'] = baseline
    result['fold'] = fold_ids
    result['gap_eur'] = predictions - df[TARGET]
    result['gap_pct'] = result.gap_eur / df[TARGET] * 100
    result['absolute_error_eur'] = result.gap_eur.abs()
    # Fit final deployment model only AFTER evaluation. Never use it to score training players.
    final_model = build_pipeline().fit(df[FEATURES], df[TARGET])
    return final_model, metrics, result


def train(df, test_size=0.2, random_state=42):
    """Compatibility wrapper; evaluation now uses deterministic player-group folds."""
    model, metrics, _ = evaluate(df)
    return model, metrics


def save_model(pipeline, path='model.joblib'):
    joblib.dump(pipeline, path)


def load_model(path='model.joblib'):
    return joblib.load(path)
