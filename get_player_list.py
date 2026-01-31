import json

def get_all_players(save_to_file=True, filename='fpl_players.json'):
    """
    Fetch all FPL players for the current season and optionally save to a file.
    
    Args:
        save_to_file (bool): Whether to save the player data to a file
        filename (str): Name of the file to save player data to
    
    Returns:
        list: List of all player dictionaries with relevant info
    """
    base_url = "https://fantasy.premierleague.com/api/"
    response = requests.get(f"{base_url}bootstrap-static/")
    response.raise_for_status()
    
    try:
        static_data = response.json()
    except ValueError as e:
        print(f"Failed to parse JSON. Status: {response.status_code}")
        raise
    
    players_data = static_data['elements']
    teams_data = {t['id']: t for t in static_data['teams']}
    
    # Create a simplified player list with key information
    all_players = []
    for p in players_data:
        player_info = {
            'id': p['id'],
            'web_name': p['web_name'],
            'full_name': f"{p['first_name']} {p['second_name']}",
            'team': teams_data[p['team']]['name'],
            'position': ['GKP', 'DEF', 'MID', 'FWD'][p['element_type'] - 1],
            'price': p['now_cost'] / 10,  # Convert to actual price
            'total_points': p['total_points'],
            'minutes': p['minutes'],
            'goals_scored': p['goals_scored'],
            'assists': p['assists'],
            'form': float(p['form']) if p['form'] else 0,
            'expected_goals': float(p['expected_goals']),
            'expected_assists': float(p['expected_assists']),
        }
        all_players.append(player_info)
    
    # Sort by total points (descending)
    all_players.sort(key=lambda x: x['total_points'], reverse=True)
    
    if save_to_file:
        with open(filename, 'w') as f:
            json.dump(all_players, f, indent=2)
        print(f"✓ Saved {len(all_players)} players to {filename}")
    
    return all_players

if __name__ == "__main__":
    get_all_players()