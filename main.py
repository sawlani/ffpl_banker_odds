import json
import time
from datetime import datetime
from fpl import get_master_stats

def load_players_from_json(filename='fpl_players.json'):
    """Load all players from the JSON file."""
    with open(filename, 'r') as f:
        return json.load(f)

def compute_odds_for_all_players(is_home=True, output_file='player_odds.json', batch_size=50, test_mode=False):
    """
    Compute odds for all players in fpl_players.json and save results.
    
    Args:
        is_home (bool): Whether to calculate for home matches
        output_file (str): Output filename for odds results
        batch_size (int): Number of players to process in each batch
        test_mode (bool): If True, only process first 10 players for testing
    """
    print("Loading players from fpl_players.json...")
    all_players = load_players_from_json()
    print(f"Loaded {len(all_players)} players")
    
    # Extract web names for all players
    player_names = [p['web_name'] for p in all_players]
    
    if test_mode:
        player_names = player_names[:10]
        print(f"\n⚠️  TEST MODE: Processing only first {len(player_names)} players")
    
    print(f"\nComputing odds for {len(player_names)} players...")
    print("This will take approximately {:.1f} minutes...".format(len(player_names) * 0.05 / 60))
    
    all_results = []
    total_batches = (len(player_names) + batch_size - 1) // batch_size
    
    start_time = time.time()
    
    # Process in batches to show progress
    for i in range(0, len(player_names), batch_size):
        batch_num = (i // batch_size) + 1
        batch = player_names[i:i + batch_size]
        
        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} players)...")
        
        try:
            batch_results = get_master_stats(batch, is_home=is_home)
            all_results.extend(batch_results)
            
            # Show progress
            processed = min(i + batch_size, len(player_names))
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = (len(player_names) - processed) / rate if rate > 0 else 0
            
            print(f"  Processed: {processed}/{len(player_names)} players")
            print(f"  Time elapsed: {elapsed/60:.1f}m | Est. remaining: {remaining/60:.1f}m")
            
        except Exception as e:
            print(f"Error processing batch {batch_num}: {e}")
            continue
    
    # Sort results by odds (ascending - best odds first)
    all_results.sort(key=lambda x: float(x['decimal_odds']))
    
    # Add metadata and save
    output_data = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_players': len(all_results),
            'is_home': is_home,
            'computation_time_seconds': round(time.time() - start_time, 2),
            'test_mode': test_mode
        },
        'players': all_results
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✓ Successfully computed odds for {len(all_results)} players")
    print(f"✓ Results saved to {output_file}")
    print(f"✓ Total time: {(time.time() - start_time)/60:.1f} minutes")
    print(f"{'='*80}")
    
    return all_results

def display_top_odds(results, n=20):
    """Display the top N players with best odds."""
    print(f"\n{'='*100}")
    print(f"TOP {n} PLAYERS - BEST ODDS TO SCORE")
    print(f"{'='*100}\n")
    
    header = f"{'Rank':<6} | {'Player':<14} | {'Base':<6} | {'Form':<7} | {'Opp':<7} | {'Prob':<7} | {'ODDS':<6} | {'DGW'}"
    print(header)
    print("-" * len(header))
    
    for idx, d in enumerate(results[:n], 1):
        dgw_indicator = f"GW{d['gameweek']} (2)" if d.get('is_double_gw', False) else ""
        opponent_adj_display = d['opponent_adj'] if d['opponent_adj'] is not None else "DGW"
        print(f"{idx:<6} | {d['player_name']:<14} | {d['base_prob']:<6} | {d['form_adj']:<7} | "
              f"{opponent_adj_display:<7} | {d['probability_pct']:<7} | {d['decimal_odds']:.2f} | {dgw_indicator}")

def display_summary_stats(results):
    """Display summary statistics about the odds."""
    print(f"\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}")
    
    # Parse probabilities
    probs = [d['final_probability'] for d in results]
    odds = [float(d['decimal_odds']) for d in results]
    
    print(f"Total players analyzed: {len(results)}")
    print(f"\nProbability to score:")
    print(f"  Average: {sum(probs)/len(probs)*100:.2f}%")
    print(f"  Median: {sorted(probs)[len(probs)//2]*100:.2f}%")
    print(f"  Max: {max(probs)*100:.2f}% ({[r['player_name'] for r in results if r['final_probability'] == max(probs)][0]})")
    print(f"  Min: {min(probs)*100:.2f}%")
    
    print(f"\nDecimal Odds:")
    print(f"  Best odds: {min(odds):.2f}")
    print(f"  Worst odds: {max(odds):.2f}")
    print(f"  Average: {sum(odds)/len(odds):.2f}")
    
    # Category breakdown
    high_prob = len([p for p in probs if p > 0.25])
    medium_prob = len([p for p in probs if 0.10 <= p <= 0.25])
    low_prob = len([p for p in probs if p < 0.10])
    
    print(f"\nPlayer Categories:")
    print(f"  High probability (>25%): {high_prob} players")
    print(f"  Medium probability (10-25%): {medium_prob} players")
    print(f"  Low probability (<10%): {low_prob} players")

if __name__ == "__main__":
    import sys
    
    # Check for test mode flag
    test_mode = '--test' in sys.argv or '-t' in sys.argv
    
    # Compute odds for all players
    results = compute_odds_for_all_players(
        is_home=True, 
        output_file='player_odds.json',
        batch_size=50,
        test_mode=test_mode
    )
    
    # Display top odds
    display_top_odds(results, n=min(30, len(results)))
    
    # Display summary statistics
    display_summary_stats(results)
    
    print(f"\n{'='*80}")
    print("Full results have been saved to player_odds.json")
    if not test_mode:
        print("Tip: Use --test flag to run in test mode (first 10 players only)")
    print(f"{'='*80}")
