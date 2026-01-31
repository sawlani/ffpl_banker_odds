# FPL Banker Odds Calculator

Calculate goal-scoring odds for Fantasy Premier League players using various metrics including xG, form, opponent strength, and more.

## Features

- **Fetch All Players**: Retrieve complete player data for the current FPL season
- **Odds Calculation**: Calculate decimal odds for players to score in their next match
- **Multi-factor Analysis**: Considers xG, form, threat, opponent defense, venue, penalties, and availability

## Quick Start

### 1. Get Player List

First, fetch all current FPL players:

```bash
python get_player_list.py
```

This creates `fpl_players.json` with ~800+ players including:
- ID, name, team, position
- Price, total points, minutes played
- Goals, assists, form
- Expected goals (xG) and expected assists (xA)

### 2. Calculate Odds for All Players

Run the main script to compute odds for all players:

```bash
# Full run (takes ~40-50 minutes for all 800+ players)
python main.py

# Test mode (first 10 players only)
python main.py --test
```

This will:
- Load all players from `fpl_players.json`
- Calculate odds for each player to score in their next match
- Display top players with best odds
- Show summary statistics
- Save complete results to `player_odds.json`

### 3. Calculate Odds for Specific Players

For quick checks of specific players:

```bash
python fpl.py
```

Or use the API directly:

```python
from fpl import get_master_stats

# Calculate odds for specific players
players = ["Haaland", "Salah", "Saka", "Palmer"]
odds_data = get_master_stats(players, is_home=True)
```

## Output

### Console Output (main.py)

```
TOP 30 PLAYERS - BEST ODDS TO SCORE

Rank   | Player         | Base   | Form    | Opp     | Prob    | ODDS
---------------------------------------------------------------------
1      | Haaland        | 0.524  | 0.008   | -0.002  | 60.8%   | 1.65
2      | Thiago         | 0.37   | 0.123   | 0.006   | 58.1%   | 1.72
3      | Watkins        | 0.268  | 0.066   | 0.002   | 40.6%   | 2.46
...

SUMMARY STATISTICS
Total players analyzed: 808

Probability to score:
  Average: 12.34%
  Median: 8.50%
  Max: 60.80% (Haaland)
  Min: 1.00%

Player Categories:
  High probability (>25%): 25 players
  Medium probability (10-25%): 120 players
  Low probability (<10%): 663 players
```

### JSON Output (player_odds.json)

```json
{
  "metadata": {
    "generated_at": "2026-01-30T22:56:53.961631",
    "total_players": 808,
    "is_home": true,
    "computation_time_seconds": 2450.2,
    "test_mode": false
  },
  "players": [
    {
      "Player": "Haaland",
      "Base": 0.524,
      "Threat": 0,
      "Form": 0.008,
      "Opp": -0.002,
      "Avail": 1,
      "Prob": "60.8%",
      "ODDS": "1.65"
    },
    ...
  ]
}
```

## Odds Calculation Components

- **Base**: Expected goals per appearance × 0.65
- **Threat**: Normalized threat score (currently disabled)
- **Form**: Recent performance relative to league average
- **Opp**: Opponent defensive strength adjustment
- **Avail**: Availability multiplier (0 if injured/unavailable)
- **Prob**: Final probability to score
- **ODDS**: Decimal odds (1/probability)

## Requirements

```bash
pip install requests
```

## Files

- `main.py`: Compute odds for all players in `fpl_players.json` and save to `player_odds.json`
- `get_player_list.py`: Fetch all FPL players and save to `fpl_players.json`
- `fpl.py`: Core odds calculation logic with example usage
- `fpl_players.json`: Generated file with all player data (committed to repo)
- `player_odds.json`: Generated odds results (gitignored)
- `fpl.ts`, `check-odds.ts`: TypeScript versions
- `fpl.ipynb`: Jupyter notebook for analysis

## Data Source

All data is fetched from the official Fantasy Premier League API:
- https://fantasy.premierleague.com/api/bootstrap-static/
- https://fantasy.premierleague.com/api/element-summary/{player_id}/

