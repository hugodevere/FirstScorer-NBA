import pandas as pd
def compute_scorer_percentage(row, home=True, x=20):
    """
    Calculate the scoring percentage of players based on their previous matches.
    
    Args:
    - row: A data row containing information about a match.
    - home (bool): If True, calculations are based on the home team. Otherwise, they are based on the away team.
    - x (int): The number of previous matches to consider when calculating the scoring percentage.
    
    Returns:
    - list: A list of scoring percentages for each player in the lineup.
    """
    # Import ast to evaluate string representations of complex data structures
    import ast
    # Determine the team's name based on the 'home' flag
    team_name = row['Home_team'] if home else row['Away_team']
    # Extract the last x games where the team has played, either as the home or away team
    last_games = df[((df['Home_team'] == team_name) | (df['Away_team'] == team_name)) 
                    & (df.index < row.name)].tail(x)
    # Ensure that the number of games extracted is at least 'x' (default 20)
    if len(last_games) < 20:
        return []
    # Determine the current match's lineup based on whether the team is playing at home or away
    team_lineup = row['Home_lineup'] if home else row['Away_lineup']
    # Count the number of times each player has been the first to score in the last x games
    scorer_counts = last_games['Player_first_score'].value_counts()
    # Compute the scoring percentage for each player in the lineup based on their scoring history in the last x games
    scorer_percentages = [round(scorer_counts.get(player, 0) / (len(last_games) - 1), 2) 
                          for player in ast.literal_eval(team_lineup)]
    return scorer_percentages

def compute_lineup_american_odds(row, home=True):
    """
    Calculate the American betting odds for players in a team's lineup based on their scoring likelihood.
    Args:
    - row: A data row containing information about a match.
    - home (bool): If True, calculations are based on the home team. Otherwise, they are based on the away team.
    Returns:
    - list: A list of American betting odds for each player in the lineup.
    """
    def custom_sort(item):
        """
        Rank players who have the same score. This method ranks duplicated ranks by player positions.
        """
        value, index = item
        # Ranking in order of likelihood to score: F1, F2, C, G1, G2 
        # where F is forward, C is center, and G is guard.
        priority = [1, 2, 0, 3, 4]
        return (value, priority[index])

    def clamp(val, min_val, max_val):
        """
        Set a boundary for a value based on provided minimum and maximum values.
        """
        return max(min_val, min(max_val, val))

    def rank_list(lst):
        """
        Rank players based on their scores.
        """
        indexed_lst = [(value, index) for index, value in enumerate(lst)]
        sorted_list = sorted(indexed_lst, key=custom_sort)
        ranks = [0] * len(lst)
        for rank, (_, index) in enumerate(sorted_list):
            ranks[index] = rank
        return ranks

     # Extract the lineup for the team (home or away).
    team_lineup = row['Home_lineup'] if home else row['Away_lineup']
    team_scores = row['home_percentages'] if home else row['home_percentages']
    
    # Rank each player based on their score.
    sorted_scores = sorted(team_scores, reverse=True)
    rank_lineup_raw = [sorted_scores.index(i) for i in team_scores]
    rank_lineup = rank_list(rank_lineup_raw)

    odds = []
    # Calculate American odds for each player based on their rank and position.
    for x in range(len(rank_lineup)):
        if x < 2:  # Forwards
            pos = 0
            odd = clamp(750 + (rank_lineup[x] * 100) + pos, 480, 900)
        elif x == 2:  # Center
            pos = -200
            odd = clamp(750 + (rank_lineup[x] * 100) + pos, 400, 600)
        else:  # Guards
            pos = 200
            odd = clamp(750 + (rank_lineup[x] * 100) + pos, 500, 1100)

        odds.append(odd)
    
    return odds



def adjust_betting_odds(row):
    """
    Adjust player odds uniformly to ensure implied probability is within bounds.
    
    Args:
    - row: A data row containing Home_odds and Away_odds
    
    Returns:
    - tuple: Two lists of adjusted odds split between home and away.
    """
    # Importing required libraries for optimization and numerical operations
    from scipy.optimize import minimize
    import numpy as np

    def objective(delta, original_odds):
        """Objective to minimize the squared difference from original odds based on uniform reduction."""
        adjusted = original_odds - delta
        return np.sum((adjusted - original_odds)**2)
    
    # The ida behind these constraints is to ensure that the adjusted betting odds produce 
    # implied probabilities within acceptable limits (110 to 120%) and are within the allowed betting range.
    def constraint1(delta, original_odds):
        """Ensure implied probability does not exceed 120% after uniform reduction."""
        adjusted = original_odds - delta
        implied_probs = 100 / (adjusted + 100)
        return 1.2 - np.sum(implied_probs)

    def constraint2(delta, original_odds):
        """Ensure implied probability is at least 110% after uniform reduction."""
        adjusted = original_odds - delta
        implied_probs = 100 / (adjusted + 100)
        return np.sum(implied_probs) - 1.1

    def constraint3(delta, original_odds):
        """Ensure no adjusted odd is less than 400."""
        adjusted = original_odds - delta
        return 400 - np.min(adjusted)
    
    def constraint4(delta, original_odds):
        """Ensure no adjusted odd is more than 1500."""
        adjusted = original_odds - delta
        return np.max(adjusted) - 1500

    def round_to_tenth(num):
        """Round a number to its nearest tenth."""
        return round(num, -1)

    # Combine home and away odds for unified processing
    original_odds = np.concatenate([row['Home_odds'], row['Away_odds']])
    
    # Setting up constraints for the optimization process
    cons = [{'type': 'ineq', 'fun': constraint1, 'args': [original_odds]},
            {'type': 'ineq', 'fun': constraint2, 'args': [original_odds]},
            {'type': 'ineq', 'fun': constraint3, 'args': [original_odds]},
            {'type': 'ineq', 'fun': constraint4, 'args': [original_odds]}]

    # Performing optimization to find the best adjustment (delta) that meets our criteria
    result = minimize(objective, [100], args=(original_odds,), constraints=cons)
    
    # Adjusting the original odds by the optimized delta value to achieve the desired properties
    delta_optimized = result.x[0]
    adjusted_all = original_odds - delta_optimized
    adjusted_odds = [round_to_tenth(odd) for odd in adjusted_all]
    
    # Splitting the adjusted odds into home and away segments and returning
    mid = len(adjusted_odds) // 2
    return adjusted_odds[:mid], adjusted_odds[mid:]
