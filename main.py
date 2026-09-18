"""Generate evaluated datasets. The GUI can also load CSVs directly."""
import argparse
from pathlib import Path
import json
import pandas as pd
from src.data_collection import collect_seasons
from src.data_processing import build_features, merge_with_transfer_values, validate_dataset
from src.model import evaluate, save_model

ROOT = Path(__file__).resolve().parent


def run_live(seasons):
    stats = build_features(collect_seasons(seasons))
    values = pd.read_csv(ROOT/'data/transfer_values.csv')
    return merge_with_transfer_values(stats, values)


def run_demo():
    return pd.read_csv(ROOT/'data/sample_dataset.csv')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['demo','live'], default='demo')
    parser.add_argument('--seasons', nargs='+', type=int, help='Explicit season start years; no historical defaults presented as current.')
    parser.add_argument('--validation', choices=['Player-held-out','Forward by season'], default='Player-held-out')
    args = parser.parse_args()
    if args.mode == 'live' and not args.seasons:
        parser.error('--mode live requires --seasons, e.g. --seasons 2024 2025')
    try:
        dataset, _ = validate_dataset(run_demo() if args.mode == 'demo' else run_live(args.seasons))
        model, metrics, results = evaluate(dataset, args.validation)
    except (ValueError, FileNotFoundError) as exc:
        parser.exit(1, f'Data error: {exc}\n')
    dataset.drop(columns=['_player_group']).to_csv(ROOT/'data/processed_dataset.csv',index=False)
    results.drop(columns=['_player_group']).to_csv(ROOT/'data/held_out_predictions.csv',index=False)
    (ROOT/'data/evaluation.json').write_text(json.dumps(metrics,indent=2,allow_nan=False))
    save_model(model, ROOT/'model.joblib')
    print('Synthetic demonstration only.' if args.mode == 'demo' else 'Scorers-only source: league coverage is incomplete.')
    print(f"Held-out MAE: EUR {metrics['mae_eur']:,.0f}; baseline MAE: EUR {metrics['baseline_mae_eur']:,.0f}")
    print('Saved processed data, held-out predictions, evaluation summary and final model.')
