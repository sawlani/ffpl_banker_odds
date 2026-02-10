import requests
import time

def get_position_floor(element_type):
    """
    Get the minimum probability floor based on player position.
    Returns floor as a decimal (e.g., 0.05 for 5%).
    """
    floors = {
        1: 0.01,   # GKP: 1% (handled separately, but included for completeness)
        2: 0.05,   # DEF: 5%
        3: 0.08,   # MID: 8%
        4: 0.125   # FWD: 12.5%
    }
    return floors.get(element_type, 0.05)  # Default to 5% if unknown

def calculate_single_fixture_prob(p, fixture, teams_data, avg_form, league_avg_def, total_mins, xg_per_app, avail_multiplier):
    """
    Calculate the probability of a player scoring in a single fixture.
    Returns the probability and all component adjustments.
    """
    player_is_home = fixture['is_home']
    opp_id = fixture['team_a'] if player_is_home else fixture['team_h']
    opponent = teams_data[opp_id]
    
    # Position check: GKPs and standard defenders get baseline low prob
    if p['element_type'] == 1:  # GKP
        return 0.01, {
            'base_prob': 0,
            'threat_adj': 0,
            'form_adj': 0,
            'opponent_adj': 0,
            'venue_adj': 0,
            'penalty_adj': 0,
            'conversion_adj': 0
        }
    elif total_mins < 90:  # Low data sample
        return 0.05, {
            'base_prob': 0,
            'threat_adj': 0,
            'form_adj': 0,
            'opponent_adj': 0,
            'venue_adj': 0,
            'penalty_adj': 0,
            'conversion_adj': 0
        }
    else:
        # 1. Base from xG/App
        base = xg_per_app * 0.65
        
        # 2. Threat & Form (normalized to league average)
        threat_adj = 0
        form_adj = (float(p['form']) / avg_form - 1) * 0.06
        
        # 3. Opponent Adjustment
        opp_def_raw = opponent['strength_defence_home'] if player_is_home else opponent['strength_defence_away']
        opponent_adj = (league_avg_def - opp_def_raw) / league_avg_def * 0.15
        
        # 4. Venue & Penalties
        venue_adj = 0.04 if player_is_home else -0.02
        # Check if player is a penalty taker from API data
        is_taker = p.get('penalties_order') == 1
        penalty = 0.035 if is_taker else 0
        
        # 5. Conversion (Goals vs xG)
        exp_goals = float(p['expected_goals'])
        conversion_adj = ((p['goals_scored'] / exp_goals - 1) * 0.03) if exp_goals > 0 else 0
        
        raw_prob = (base + threat_adj + form_adj + opponent_adj + venue_adj + penalty + conversion_adj)
        position_floor = get_position_floor(p['element_type'])
        final_prob = max(position_floor, min(raw_prob * avail_multiplier, 0.75))
        
        return final_prob, {
            'base_prob': base,
            'threat_adj': threat_adj,
            'form_adj': form_adj,
            'opponent_adj': opponent_adj,
            'venue_adj': venue_adj,
            'penalty_adj': penalty,
            'conversion_adj': conversion_adj,
            'raw_prob': raw_prob
        }

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
        
        # Get fixture data - check for double gameweek
        all_fixtures = summary.get('fixtures', [])
        if not all_fixtures:
            continue  # Skip if no fixtures found
        
        # Filter for upcoming fixtures (those with an event number)
        upcoming_fixtures = [f for f in all_fixtures if f.get('event') is not None]
        if not upcoming_fixtures:
            continue  # Skip if no upcoming fixtures
        
        # Check for double gameweek (multiple fixtures in the same gameweek)
        next_gw = upcoming_fixtures[0].get('event')
        fixtures_in_next_gw = [f for f in upcoming_fixtures if f.get('event') == next_gw]
        is_double_gw = len(fixtures_in_next_gw) > 1
        
        # Availability Check (for all cases)
        chance = p['chance_of_playing_next_round']
        avail_multiplier = 1 if (chance is None or chance > 0) else 0
        
        # Calculate probabilities for each fixture in the gameweek
        fixture_probs = []
        fixture_details = []
        
        for fixture in fixtures_in_next_gw:
            prob, components = calculate_single_fixture_prob(
                p, fixture, teams_data, avg_form, league_avg_def, 
                total_mins, xg_per_app, avail_multiplier
            )
            fixture_probs.append(prob)
            
            # Store fixture details with individual adjustments
            player_is_home = fixture['is_home']
            opp_id = fixture['team_a'] if player_is_home else fixture['team_h']
            opponent = teams_data[opp_id]
            fixture_details.append({
                'opponent': opponent.get('name', 'Unknown'),
                'is_home': player_is_home,
                'probability': round(prob, 4),
                'opponent_adj': round(components['opponent_adj'], 3),
                'venue_adj': round(components['venue_adj'], 3),
                'base_prob': round(components['base_prob'], 3),
                'form_adj': round(components['form_adj'], 3),
                'threat_adj': round(components['threat_adj'], 3),
                'penalty_adj': round(components['penalty_adj'], 3),
                'conversion_adj': round(components['conversion_adj'], 3),
                'components': components  # Keep full components for averaging
            })
        
        # Add probabilities together for DGW (as requested)
        final_prob = sum(fixture_probs)
        # Cap at reasonable maximum (e.g., 0.90 for very high combined probability)
        final_prob = min(final_prob, 0.90)
        
        # Use first fixture for display purposes
        first_fixture = fixtures_in_next_gw[0]
        player_is_home = first_fixture['is_home']
        opp_id = first_fixture['team_a'] if player_is_home else first_fixture['team_h']
        opponent = teams_data[opp_id]
        opponent_name = opponent.get('name', 'Unknown')
        is_home_match = player_is_home
        
        # Get components from first fixture for display (or average if DGW)
        if is_double_gw:
            # Average components across both fixtures for display
            avg_components = {
                'base_prob': sum(d['components']['base_prob'] for d in fixture_details) / len(fixture_details),
                'threat_adj': sum(d['components']['threat_adj'] for d in fixture_details) / len(fixture_details),
                'form_adj': sum(d['components']['form_adj'] for d in fixture_details) / len(fixture_details),
                'opponent_adj': sum(d['components']['opponent_adj'] for d in fixture_details) / len(fixture_details),
                'venue_adj': sum(d['components']['venue_adj'] for d in fixture_details) / len(fixture_details),
                'penalty_adj': sum(d['components']['penalty_adj'] for d in fixture_details) / len(fixture_details),
                'conversion_adj': sum(d['components']['conversion_adj'] for d in fixture_details) / len(fixture_details),
                'raw_prob': sum(d['components'].get('raw_prob', 0) for d in fixture_details) / len(fixture_details)
            }
        else:
            avg_components = fixture_details[0]['components']
        
        # Check if player is a penalty taker
        is_taker = p.get('penalties_order') == 1

        # --- ODDS CALCULATION ---
        decimal_odds = round(1 / final_prob, 2) if final_prob > 0 else 99.0
        
        # Build opponents list for DGW
        opponents_list = [d['opponent'] for d in fixture_details]
        opponents_display = " & ".join(opponents_list) if is_double_gw else opponent_name
        
        results.append({
            # Player identification
            "player_id": p['id'],
            "player_name": p['web_name'],
            "full_name": f"{p['first_name']} {p['second_name']}",
            "team": teams_data[p['team']]['name'],
            "position": ['GKP', 'DEF', 'MID', 'FWD'][p['element_type'] - 1],
            
            # Match context
            "next_opponent": opponents_display,
            "is_home": is_home_match,
            "is_double_gw": is_double_gw,
            "gameweek": next_gw,
            "num_fixtures": len(fixtures_in_next_gw),
            "opponents": opponents_list,
            
            # Raw stats
            "total_minutes": total_mins,
            "appearances": apps,
            "avg_minutes_per_app": round(avg_mins_per_app, 1),
            "goals_scored": p['goals_scored'],
            "expected_goals": float(p['expected_goals']),
            "expected_goals_per_90": float(p['expected_goals_per_90']),
            "xg_per_app": round(xg_per_app, 3),
            "form": float(p['form']),
            "threat": float(p['threat']),
            "penalties_order": p.get('penalties_order'),
            "penalties_scored": p.get('penalties_scored', 0),
            "is_penalty_taker": is_taker,
            
            # Odds components (averaged for DGW, but opponent_adj and venue_adj removed for DGW)
            "base_prob": round(avg_components['base_prob'], 3),
            "threat_adj": round(avg_components['threat_adj'], 3),
            "form_adj": round(avg_components['form_adj'], 3),
            "opponent_adj": round(avg_components['opponent_adj'], 3) if not is_double_gw else None,
            "venue_adj": round(avg_components['venue_adj'], 3) if not is_double_gw else None,
            "penalty_adj": round(avg_components['penalty_adj'], 3),
            "conversion_adj": round(avg_components['conversion_adj'], 3),
            "raw_prob_before_avail": round(avg_components.get('raw_prob', 0), 3),
            "availability_multiplier": avail_multiplier,
            "chance_of_playing": chance,
            
            # Individual fixture probabilities (for DGW)
            "fixture_probabilities": [round(prob, 4) for prob in fixture_probs] if is_double_gw else None,
            
            # Individual fixture details (for DGW - only opponent, opponent_adj, and venue_adj)
            "fixture_details": [
                {
                    "opponent": d['opponent'],
                    "opponent_adj": d['opponent_adj'],
                    "venue_adj": d['venue_adj']
                }
                for d in fixture_details
            ] if is_double_gw else None,
            
            # Final results
            "final_probability": round(final_prob, 4),
            "probability_pct": f"{final_prob:.1%}",
            "decimal_odds": decimal_odds
        })
        # Respect API rate limits
        time.sleep(0.05)

    return results

if __name__ == "__main__":
    # Sanity check list (40+ players)
    players = [
        "Haaland", "Salah", "Saka", "Palmer", "Son", "Watkins", "Isak", "Wood", "Jackson", 
        "Evanilson", "Welbeck", "Pedro", "Chiesa", "Delap", "Jota", "Raya", "Pickford", 
        "White", "Saliba", "Guiu", "Jesus", "Thiago"
    ]

    data = get_master_stats(players)

    # Display Results
    header = f"{'Player':<14} | {'Base':<6} | {'Threat':<7} | {'Form':<7} | {'Opp':<7} | {'Avail':<6} | {'Prob':<7} | {'ODDS':<6} | {'DGW'}"
    print(header)
    print("-" * len(header))
    for d in sorted(data, key=lambda x: float(x['decimal_odds'])):
        dgw_indicator = f"GW{d['gameweek']} (2)" if d.get('is_double_gw', False) else ""
        opponent_adj_display = d['opponent_adj'] if d['opponent_adj'] is not None else "DGW"
        print(f"{d['player_name']:<14} | {d['base_prob']:<6} | {d['threat_adj']:<7} | {d['form_adj']:<7} | {opponent_adj_display:<7} | {d['availability_multiplier']:<6} | {d['probability_pct']:<7} | {d['decimal_odds']:.2f} | {dgw_indicator}")