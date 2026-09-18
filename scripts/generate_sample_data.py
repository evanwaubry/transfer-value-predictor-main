"""
Generates data/sample_dataset.csv: real Premier League player names/positions
paired with RANDOM, FORMULA-GENERATED stats and values. This is demo data only
so the pipeline (main.py --mode demo) runs end to end without an API key or a
purchased dataset. It is NOT real performance data or real transfer values --
swap in --mode live once you have an API key and a transfer_values.csv.
"""
from pathlib import Path
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

# (name, position, approx age, team) -- names/positions/teams are public
# knowledge; ages are approximate for demo purposes.
PLAYERS = [
    ("Erling Haaland", "Attacker", 24, "Manchester City"),
    ("Mohamed Salah", "Attacker", 32, "Liverpool"),
    ("Bukayo Saka", "Attacker", 23, "Arsenal"),
    ("Cole Palmer", "Attacker", 23, "Chelsea"),
    ("Ollie Watkins", "Attacker", 28, "Aston Villa"),
    ("Alexander Isak", "Attacker", 25, "Newcastle United"),
    ("Son Heung-min", "Attacker", 32, "Tottenham Hotspur"),
    ("Phil Foden", "Midfielder", 25, "Manchester City"),
    ("Martin Odegaard", "Midfielder", 26, "Arsenal"),
    ("Declan Rice", "Midfielder", 26, "Arsenal"),
    ("Bruno Fernandes", "Midfielder", 30, "Manchester United"),
    ("Rodri", "Midfielder", 28, "Manchester City"),
    ("Kevin De Bruyne", "Midfielder", 33, "Manchester City"),
    ("Moises Caicedo", "Midfielder", 23, "Chelsea"),
    ("James Maddison", "Midfielder", 28, "Tottenham Hotspur"),
    ("Youri Tielemans", "Midfielder", 27, "Aston Villa"),
    ("Trent Alexander-Arnold", "Defender", 26, "Liverpool"),
    ("William Saliba", "Defender", 23, "Arsenal"),
    ("Virgil van Dijk", "Defender", 33, "Liverpool"),
    ("Reece James", "Defender", 25, "Chelsea"),
    ("Levi Colwill", "Defender", 21, "Chelsea"),
    ("Gabriel Magalhaes", "Defender", 26, "Arsenal"),
    ("Kieran Trippier", "Defender", 34, "Newcastle United"),
    ("Ben Chilwell", "Defender", 27, "Chelsea"),
    ("Alisson Becker", "Goalkeeper", 32, "Liverpool"),
    ("Ederson", "Goalkeeper", 31, "Manchester City"),
    ("David Raya", "Goalkeeper", 29, "Arsenal"),
    ("Jordan Pickford", "Goalkeeper", 30, "Everton"),
    ("Nick Pope", "Goalkeeper", 32, "Newcastle United"),
    ("Bernardo Silva", "Midfielder", 30, "Manchester City"),
    ("Jarrod Bowen", "Attacker", 27, "West Ham United"),
    ("Anthony Gordon", "Attacker", 23, "Newcastle United"),
    ("Morgan Rogers", "Midfielder", 22, "Aston Villa"),
    ("Chris Wood", "Attacker", 33, "Nottingham Forest"),
    ("Justin Kluivert", "Attacker", 25, "Bournemouth"),
    ("Amad Diallo", "Attacker", 22, "Manchester United"),
    ("Matheus Cunha", "Attacker", 25, "Manchester United"),
    ("Cody Gakpo", "Attacker", 25, "Liverpool"),
    ("Dominik Szoboszlai", "Midfielder", 24, "Liverpool"),
    ("Antoine Semenyo", "Attacker", 25, "Bournemouth"),
]

POSITION_GOAL_LAMBDA = {"Attacker": 12, "Midfielder": 5, "Defender": 2, "Goalkeeper": 0}
POSITION_ASSIST_LAMBDA = {"Attacker": 6, "Midfielder": 7, "Defender": 2, "Goalkeeper": 0}


def synthetic_value(goals: int, assists: int, appearances: int, age: float) -> float:
    base = 5_000_000
    base += goals * 1_800_000
    base += assists * 900_000
    base += appearances * 150_000
    age_factor = max(0.4, 1.4 - 0.035 * max(age - 22, 0))
    value = base * age_factor
    noise = rng.normal(1.0, 0.12)
    return float(max(1_000_000, value * noise))


def main():
    rows = []
    for name, position, age, team in PLAYERS:
        goals = int(rng.poisson(POSITION_GOAL_LAMBDA[position]))
        assists = int(rng.poisson(POSITION_ASSIST_LAMBDA[position]))
        appearances = int(rng.integers(15, 38))
        value = synthetic_value(goals, assists, appearances, age)
        rows.append({
            "name": name,
            "data_kind": "synthetic",
            "position": position,
            "age": age,
            "team": team,
            "season": 2024,
            "appearances": appearances,
            "goals": goals,
            "assists": assists,
            "transfer_value_eur": round(value, -3),  # round to nearest 1,000
        })

    df = pd.DataFrame(rows)
    df.to_csv(Path(__file__).resolve().parents[1] / "data/sample_dataset.csv", index=False)
    print(f"Wrote {len(df)} rows to data/sample_dataset.csv")


if __name__ == "__main__":
    main()
