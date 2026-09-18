"""Explicit validation and season-aligned, exact identity joins."""
import unicodedata
import numpy as np
import pandas as pd

TARGET = 'transfer_value_eur'
REQUIRED = ['name', 'position', 'age', 'team', 'season', 'appearances', 'goals', 'assists', TARGET]


def normalize_name(value):
    return ' '.join(unicodedata.normalize('NFKC', str(value)).casefold().split())


def validate_dataset(frame):
    df = frame.copy().reset_index(drop=True)
    missing = set(REQUIRED) - set(df.columns)
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(sorted(missing)))
    if len(df) < 10:
        raise ValueError('At least 10 player-season rows are required for evaluation.')
    for col in ['name', 'position', 'team']:
        if df[col].isna().any() or df[col].astype(str).str.strip().eq('').any():
            raise ValueError(f'{col}: blank values must be corrected.')
        df[col] = df[col].astype(str).str.strip()
    aliases = {'fw': 'Attacker', 'forward': 'Attacker', 'attacker': 'Attacker', 'mf': 'Midfielder', 'midfield': 'Midfielder', 'midfielder': 'Midfielder', 'df': 'Defender', 'defence': 'Defender', 'defender': 'Defender', 'gk': 'Goalkeeper', 'goalkeeper': 'Goalkeeper'}
    df['position'] = df.position.str.casefold().map(aliases)
    if df.position.isna().any():
        raise ValueError('Use position Attacker, Midfielder, Defender or Goalkeeper (FW/MF/DF/GK accepted).')
    for col in ['age', 'season', 'appearances', 'goals', 'assists', TARGET]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        if not np.isfinite(df[col]).all():
            raise ValueError(f'{col}: every row needs a finite number; missing is not zero.')
    for col in ['goals', 'assists', 'appearances', 'season']:
        if ((df[col] % 1 != 0) | (df[col] < 0)).any():
            raise ValueError(f'{col}: expected nonnegative whole numbers.')
    if not df.age.between(14, 50).all() or not df.season.between(1992, 2100).all():
        raise ValueError('Check age (14–50) and season (start year, e.g. 2025).')
    if (df[TARGET] <= 0).any():
        raise ValueError('Values must be positive EUR amounts, not millions or formatted currency strings.')
    if (df.appearances > 42).any() or ((df.appearances == 0) & ((df.goals > 0) | (df.assists > 0))).any():
        raise ValueError('Inconsistent appearances: check league-only season totals and zero-appearance rows.')
    identity = df.name.map(normalize_name)
    if 'player_id' in df:
        if df.player_id.isna().any():
            raise ValueError('player_id must be complete when supplied.')
        identity = df.player_id.astype(str)
        if df.groupby(df.name.map(normalize_name)).player_id.nunique().max() > 1:
            raise ValueError('Ambiguous names map to multiple IDs; resolve identities before modeling.')
    df['_player_group'] = identity
    if df.duplicated(['_player_group', 'season']).any():
        raise ValueError('Duplicate player-season rows. Aggregate club stints and resolve duplicate identities first.')
    if identity.nunique() < 10:
        raise ValueError('At least 10 distinct players are required.')
    warnings = []
    if len(df) < 200:
        warnings.append('Small sample: results are exploratory; collect several hundred player-seasons.')
    if 'player_id' not in df:
        warnings.append('Players are grouped by exact normalized name. Stable cross-source IDs are safer.')
    if not {'stats_as_of', 'valuation_date'}.issubset(df.columns):
        warnings.append('Snapshot dates are missing; season labels alone cannot verify temporal alignment.')
    else:
        stats = pd.to_datetime(df.stats_as_of, errors='coerce', utc=True)
        values = pd.to_datetime(df.valuation_date, errors='coerce', utc=True)
        if stats.isna().any() or values.isna().any() or (stats > values).any():
            raise ValueError('Dates must be valid and stats_as_of must not follow valuation_date.')
    warnings.append('Goals and assists do not capture defensive or goalkeeper performance. Position alone does not fix this.')
    return df, warnings


def compute_age(date_of_birth, as_of_year):
    if not date_of_birth:
        return None
    return round((pd.Timestamp(year=int(as_of_year), month=8, day=1) - pd.to_datetime(date_of_birth)).days / 365.25, 1)


def build_features(stats_rows):
    if not stats_rows:
        raise ValueError('The API returned no scorers.')
    df = pd.DataFrame(stats_rows)
    df['age'] = df.apply(lambda r: compute_age(r['date_of_birth'], r['season']), axis=1)
    return df


def merge_with_transfer_values(stats_df, values_df):
    if 'season' not in values_df or TARGET not in values_df:
        raise ValueError('Value CSV requires season and transfer_value_eur; timeless values cannot be joined to historical stats.')
    left, right = stats_df.copy(), values_df.copy()
    key = 'player_id' if 'player_id' in left and 'player_id' in right else 'name'
    if key not in right:
        raise ValueError('Provide player_id from the same ID system, or exact player name.')
    for df in [left, right]:
        if df[key].isna().any():
            raise ValueError('Join identities cannot be blank.')
        df['_join'] = df[key].map(normalize_name) if key == 'name' else df[key].astype(str).str.strip()
        df['season'] = pd.to_numeric(df.season, errors='raise')
        if df.duplicated(['_join', 'season']).any():
            raise ValueError('Duplicate identity-season keys; resolve before joining.')
    columns = ['_join', 'season', TARGET] + [c for c in ['valuation_date', 'value_source'] if c in right]
    merged = left.merge(right[columns], on=['_join', 'season'], how='left', validate='one_to_one', indicator=True)
    missing = merged.loc[merged['_merge'] != 'both', 'name'].tolist()
    if missing:
        raise ValueError('Unmatched players; use explicit corrected names or shared IDs: ' + ', '.join(missing[:15]))
    return merged.drop(columns=['_join', '_merge'])
