import requests
import time

def get_master_stats(player_names, is_home=True):
    base_url = "https://fantasy.premierleague.com/api/"
    response = requests.get(f"{base_url}bootstrap-static/")
    response.raise_for_status()  # Raise an exception for bad status codes
    
    # Check content type
    content_type = response.headers.get('Content-Type', '')
    if 'application/json' not in content_type:
        print(f"Warning: Unexpected content type: {content_type}")
        print(f"Response preview: {response.text[:500]}")
    
    try:
        static_data = response.json()
    except ValueError as e:
        print(f"Failed to parse JSON. Status: {response.status_code}")
        print(f"Response text (first 500 chars): {response.text[:500]}")
        raise
    
    if not isinstance(static_data, dict):
        raise TypeError(f"Expected dict, got {type(static_data)}. Response preview: {str(static_data)[:200]}")
    
    players_data = static_data['elements']
    teams_data = {t['id']: t for t in static_data['teams']}
    
    # --- 1. LEAGUE WIDE AVERAGES (Normalization Baselines) ---
    # We only baseline players with > 270 mins (3 full games) to get 'standard' starters
    starters = [p for p in players_data if p['minutes'] > 270]
    avg_threat = sum(float(p['threat']) for p in starters) / len(starters)
    avg_form = sum(float(p['form']) for p in starters) / len(starters)
    
    all_def = [t['strength_defence_home'] for t in static_data['teams']] + \
              [t['strength_defence_away'] for t in static_data['teams']]
    league_avg_def = sum(all_def) / len(all_def)

    results = []

    for name in player_names:
        # Search for player by last name
        p = next((p for p in players_data if name.lower() in p['second_name'].lower() 
                  or name.lower() in p['web_name'].lower()), None)
        
        if not p: continue
            
        # Fetch individual history
        summary = requests.get(f"{base_url}element-summary/{p['id']}/").json()
        history = summary.get('history', [])
        
        # --- PLAYER METRICS ---
        total_mins = sum(h['minutes'] for h in history)
        apps = len([h for h in history if h['minutes'] > 0])
        avg_mins_per_app = (total_mins / apps) if apps > 0 else 0
        xg_per_app = (float(p['expected_goals_per_90']) * avg_mins_per_app) / 90
        
        # --- CALCULATE COMPONENTS ---
        
        # Availability Check (for all cases)
        chance = p['chance_of_playing_next_round']
        avail_multiplier = 1 if (chance is None or chance > 0) else 0
        
        # Position check: GKPs and standard defenders get baseline low prob
        if p['element_type'] == 1: # GKP
            final_prob = 0.01
        elif total_mins < 90: # Low data sample
            final_prob = 0.05
        else:
            # 1. Base from xG/App
            base = xg_per_app * 0.65
            
            # 2. Threat & Form (normalized to league average)
            #threat_adj = (float(p['threat']) / avg_threat - 1) * 0.08
            threat_adj = 0
            form_adj = (float(p['form']) / avg_form - 1) * 0.06
            
            # 3. Opponent Adjustment
            next_fix = summary['fixtures'][0] if summary['fixtures'] else None
            opp_id = next_fix['team_a'] if next_fix['is_home'] else next_fix['team_h'] if next_fix else 1
            opponent = teams_data[opp_id]
            opp_def_raw = opponent['strength_defence_home'] if is_home else opponent['strength_defence_away']
            opponent_adj = (league_avg_def - opp_def_raw) / league_avg_def * 0.15 
            
            # 4. Venue & Penalties
            venue_adj = 0.04 if is_home else -0.02
            # Check if player is a penalty taker from API data
            is_taker = ((p.get('penalties_order') is not None and p.get('penalties_order', 0) > 0) or
                       p.get('penalties_scored', 0) > 0)
            penalty = 0.035 if is_taker else 0
            
            # 5. Conversion (Goals vs xG)
            exp_goals = float(p['expected_goals'])
            conversion_adj = ((p['goals_scored'] / exp_goals - 1) * 0.03) if exp_goals > 0 else 0
            
            raw_prob = (base + threat_adj + form_adj + opponent_adj + venue_adj + penalty + conversion_adj)
            final_prob = max(0.05, min(raw_prob * avail_multiplier, 0.75))

        # --- ODDS CALCULATION ---
        decimal_odds = round(1 / final_prob, 2) if final_prob > 0 else 99.0

        results.append({
            "Player": p['web_name'],
            "Base": round(xg_per_app * 0.65, 3),
            "Threat": round(threat_adj, 3) if 'threat_adj' in locals() else 0,
            "Form": round(form_adj, 3) if 'form_adj' in locals() else 0,
            "Opp": round(opponent_adj, 3) if 'opponent_adj' in locals() else 0,
            "Avail": avail_multiplier,
            "Prob": f"{final_prob:.1%}",
            "ODDS": f"{decimal_odds:.2f}"
        })
        # Respect API rate limits
        time.sleep(0.05)

    return results

# Sanity check list (40+ players)
players = [
    "Haaland", "Salah", "Saka", "Palmer", "Son", "Watkins", "Isak", "Wood", "Jackson", 
    "Solanke", "Mbeumo", "Havertz", "Diaz", "Gakpo", "Bowen", "Gordon", "Fernandes", 
    "Rashford", "Garnacho", "Johnson", "Kulusevski", "Cunha", "Larsen", "Wissa", 
    "Delap", "Raul", "Savio", "Foden", "Martinelli", "Eze", "Rogers", "Semenyo", 
    "Evanilson", "Welbeck", "Pedro", "Chiesa", "Delap", "Jota", "Raya", "Pickford", 
    "White", "Saliba", "Guiu", "Jesus", "Thiago"
]

data = get_master_stats(players)

# Display Results
header = f"{'Player':<14} | {'Base':<6} | {'Threat':<7} | {'Form':<7} | {'Opp':<7} | {'Avail':<6} | {'Prob':<7} | {'ODDS'}"
print(header)
print("-" * len(header))
for d in sorted(data, key=lambda x: float(x['ODDS'])):
    print(f"{d['Player']:<14} | {d['Base']:<6} | {d['Threat']:<7} | {d['Form']:<7} | {d['Opp']:<7} | {d['Avail']:<6} | {d['Prob']:<7} | {d['ODDS']}")