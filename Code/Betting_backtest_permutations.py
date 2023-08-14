def Betting_backtest_permutations(df, position_range=None, rank_range=None, random_dates=2,combinations_n=2):
    """
    This function backtests of parlay betting strategy based on either player positions or their score rankings.

    Parameters:
    - df: DataFrame containing the game data.
    - position_range: Tuple indicating the range of player positions to consider.
    - rank_range: Rank of the players to consider (e.g. top 5 players by score).
    - random_dates: Number of random dates to backtest on.
    - combinations_n: Number of game combinations to test.

    Returns: 
    - bank_account: Final value in the bank account after backtesting. 
    - win_loss_ratio: Proportion of successful bets made. 
    """

    import pandas as pd
    import random
    import ast
    import numpy as np
    #Extracting number of bets per team
    if rank_range is not None:
        n = rank_range
    else:
        n = len(list(range(position_range[0],position_range[1])))
    # This function is used for sorting players based on their likelihood to score, given their position.
    def custom_sort(item):
        """Sort function to rank players by their likelihood to score."""
        value, index = item
        # Ranking in order of more likely to score F1,F2,C,G1,G2 
        # where F is forward, C center and G Guard.
        priority = [1, 2, 0, 3, 4]
        return (value, priority[index])

    # This function clamps a value between a minimum and maximum limit.
    def clamp(val, min_val, max_val):
        """Clamp function to set max and min boundaries for each player position."""
        return max(min_val, min(max_val, val))

    # This function generates a rank list based on the custom_sort criteria. 
    def rank_list(lst):
        """Generate a rank list based on custom_sort criteria."""
        indexed_lst = [(value, index) for index, value in enumerate(lst)]
        sorted_list = sorted(indexed_lst, key=custom_sort)
        ranks = [0] * len(lst)
        for rank, (_, index) in enumerate(sorted_list):
            ranks[index] = rank
        return ranks

    # This function reorders a list of player names and their odds based on the given rank.
    def reorder_list(names, odds, rank):
        """Reorder names and odds based on given ranks."""
        reordered_names = [name for _, name in sorted(zip(rank, names))]
        reordered_odds = [odd for _, odd in sorted(zip(rank, odds))]
        return reordered_names, reordered_odds
    
    # This function extracts the starting lineups and odds for a particular game based on score ranking.
    def extract_data_based_on_rank(row, rank_range):
        """Extract starting lineups and odds based on score rank."""
        home_players, home_odds = process_team_ranking(row, 'Home', rank_range)
        away_players, away_odds = process_team_ranking(row, 'Away', rank_range)
        return home_players[:rank_range] + away_players[:rank_range], home_odds[:rank_range] + away_odds[:rank_range], ast.literal_eval(row['Home_odds'])+ast.literal_eval(row['Away_odds'])

    # This function processes and reorders players and odds based on the scoring rank within a team.
    def process_team_ranking(row, team_side, rank_range):
        """Compute player rankings and reorder players and odds."""
        players = ast.literal_eval(row[f'{team_side}_lineup'])
        odds = ast.literal_eval(row[f'{team_side}_odds'])
        scores = ast.literal_eval(row[f'{team_side.lower()}_percentages'])
        rank_lineup = rank_list(scores)
        players, odds = reorder_list(players, odds, rank_lineup)
        return players, odds

    # This function extracts the starting lineups and odds for a particular game based on player positions.
    def extract_data_based_on_position(row, position_range):
        """Extract starting lineups and odds based on player positions."""
        home_players = ast.literal_eval(row['Home_lineup'])[position_range[0]:position_range[1]]
        away_players = ast.literal_eval(row['Away_lineup'])[position_range[0]:position_range[1]]
        home_odds = ast.literal_eval(row['Home_odds'])[position_range[0]:position_range[1]]
        away_odds = ast.literal_eval(row['Away_odds'])[position_range[0]:position_range[1]]
        return home_players + away_players, home_odds + away_odds, ast.literal_eval(row['Home_odds'])+ast.literal_eval(row['Away_odds'])
    
    # This function converts odds values between American and decimal formats.
    def odds_conversion(value,american_odds=True):
        """Convert american probability to decimal probability and viceversa"""
        if american_odds:
            if value > 0:
                return 100 / (value + 100)
            elif value < 0:
                return -value / (value - 100)
        else:
            if 0 < value < 1:
                if value > 0.5:
                    return round(- (value / (1 - value)) * 100,2)
                else:
                    return round((1 - value) / value * 100,2)
            else:
                raise ValueError("Probability should be decimal")
    
    # This function calculates combined odds given a list of individual odds.
    def calculate_odds(odds_list, american_odds=True):
        total = 1
        for odd in odds_list:
            total *= odds_conversion(odd, american_odds)
        return odds_conversion(total, american_odds=False)


    # The following section conducts the main backtesting, where we iterate through each date, 
    # select games, compute odds, place bets, and then calculate the win/loss ratio.
    # Initializing the bank account with a starting balance.
    bank_account = 1000 
    # Counter for the number of successful bets made.
    successful_bets = 0
    # For each selected game on a given date, we'll extract player data, odds, and scoring players.
    dates = random.sample(list(df['Game_date']), random_dates)
    for date in dates:
        games_selected = random.sample(list(games_df[games_df['Game_date'] == date].index),combinations_n)
        scoring_players = []
        selected_players = []
        selected_odds = []
        all_odds = []
        for gameid in games_selected:
            row = df.loc[gameid]
            if position_range: 
                players, odds,all_game_odds = extract_data_based_on_position(row, position_range)
            else:
                players, odds,all_game_odds = extract_data_based_on_rank(row, rank_range)
            scoring_players.append(row['Player_first_score'])
            selected_players.append(players)
            selected_odds.append(odds)
            all_odds.append(all_game_odds)

        # Next, we'll compute all possible player combinations for betting and calculate 
        # the expected payout for each combination based on the odds.
        team_indexes = [list(range(0,n*2)) for x in range(0,combinations_n)]
        combinations = list(product(*team_indexes))
        total_bet = 0.02 * bank_account
        try:
            index_scorers = tuple([g.index(x) for g, x in zip(selected_players, scoring_players)])
            combinations_odds = []
            for combination in combinations:
                odds_list = [selected_odds[i][combination[i]] for i in range(combinations_n)]
                combinations_odds.append([combination, calculate_odds(odds_list)])
            odds = [x[1] for x in combinations_odds]
            bet_size = total_bet / len(combinations)

            # Based on the actual scoring players, we'll calculate our win or loss for the given date.
            result = [item[1] for item in combinations_odds if item[0] == index_scorers] #Identify if any combination we bet has the actual scoring combination
            if len(result) > 0:
                win_loss = (bet_size * ((result[0]) / 100))
                successful_bets += 1
            else:
                win_loss = 0
            bank_account += win_loss - total_bet
            if bank_account <= 0:
                break
        except:
            bank_account += 0 - total_bet
            if bank_account <= 0:
                break

    win_loss_ratio = successful_bets / len(dates)
    # The function returns the final bank account balance and the win/loss ratio after the backtest.
    return bank_account, win_loss_ratio