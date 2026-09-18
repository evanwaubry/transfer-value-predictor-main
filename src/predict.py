"""CLI reports held-out estimates, never in-sample fitted values."""
import argparse
from pathlib import Path
import pandas as pd
from src.model import evaluate, TARGET


def predict_player(df, player_name, season=None, strategy='Player-held-out'):
    _, _, evaluated = evaluate(df,strategy)
    row = evaluated[evaluated.name.str.casefold() == player_name.casefold()]
    if season is not None:
        row = row[row.season == season]
    if len(row) != 1:
        raise ValueError('Specify an exact unique player name and --season if needed.')
    r = row.iloc[0]
    if pd.isna(r.predicted_value_eur):
        raise ValueError('No forward estimate for the earliest training season.')
    print(f"{r['name']} · {int(r.season)} · {r.team}")
    print(f'Listed: EUR {r[TARGET]:,.0f}; held-out estimate: EUR {r.predicted_value_eur:,.0f}')
    print(f'Model gap: {r.gap_pct:+.1f}%. This does not establish fair market value.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('player')
    parser.add_argument('--season',type=int)
    parser.add_argument('--data',default=str(Path(__file__).resolve().parents[1]/'data/sample_dataset.csv'))
    parser.add_argument('--validation',choices=['Player-held-out','Forward by season'],default='Player-held-out')
    args=parser.parse_args()
    try:
        predict_player(pd.read_csv(args.data),args.player,args.season,args.validation)
    except ValueError as exc:
        parser.exit(1,f'{exc}\n')
