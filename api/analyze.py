"""Vercel serverless function: validate a CSV, evaluate the Ridge model, return JSON.

POST body: {"csv": "<full csv text>", "strategy": "Player-held-out" | "Forward by season"}
Response:  {"ok": true, "warnings": [...], "metrics": {...}, "rows": [...],
            "model": {"intercept": float, "numeric": {...}, "position": {...}}, "target": "..."}

Reuses the exact validation + Ridge pipeline from src/, so results here match the
original Streamlit app row-for-row. The fitted model's coefficients are exported so
the frontend "Scenario Lab" can compute what-if predictions instantly in the browser
without another round trip.
"""
from http.server import BaseHTTPRequestHandler
import io
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data_processing import validate_dataset  # noqa: E402
from src.model import evaluate, NUMERIC_FEATURES, TARGET  # noqa: E402


def _model_params(model):
    prep = model.named_steps['preprocess']
    ridge = model.named_steps['model']
    scaler = prep.named_transformers_['numeric']
    ohe = prep.named_transformers_['position']
    n_num = len(NUMERIC_FEATURES)
    numeric = {
        feat: {
            'mean': float(scaler.mean_[i]),
            'std': float(scaler.scale_[i]),
            'coef': float(ridge.coef_[i]),
        }
        for i, feat in enumerate(NUMERIC_FEATURES)
    }
    categories = ohe.categories_[0].tolist()
    position = {cat: float(ridge.coef_[n_num + j]) for j, cat in enumerate(categories)}
    return {'intercept': float(ridge.intercept_), 'numeric': numeric, 'position': position}


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
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
            body = self.rfile.read(length) if length else b'{}'
            payload = json.loads(body or b'{}')
            csv_text = payload.get('csv')
            strategy = payload.get('strategy', 'Player-held-out')
            if not csv_text or not str(csv_text).strip():
                raise ValueError('No CSV data was provided.')
            if strategy not in ('Player-held-out', 'Forward by season'):
                raise ValueError('Unknown validation strategy.')

            raw = pd.read_csv(io.StringIO(csv_text))
            dataset, warnings = validate_dataset(raw)
            model, metrics, result = evaluate(dataset, strategy)

            clean = result.drop(columns=['_player_group'], errors='ignore')
            rows = json.loads(clean.to_json(orient='records'))

            response = {
                'ok': True,
                'warnings': warnings,
                'metrics': metrics,
                'rows': rows,
                'model': _model_params(model),
                'target': TARGET,
                'row_count': int(len(dataset)),
                'player_count': int(dataset['_player_group'].nunique()),
            }
            self._send(200, response)
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError, KeyError) as exc:
            self._send(400, {'ok': False, 'error': str(exc)})
        except Exception as exc:  # noqa: BLE001 - surface a safe message either way
            self._send(500, {'ok': False, 'error': f'Unexpected server error: {exc}'})
