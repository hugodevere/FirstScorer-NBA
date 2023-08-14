import re
import pandas as pd
from nba_api.stats.endpoints import commonplayerinfo, playbyplayv2, playercareerstats
from tqdm.auto import tqdm
import time
from nba_api.stats.endpoints import leaguegamelog
import os
import pickle
class GameIDFetcher:
    def __init__(self, cache_dir='nba_cache', delay=1.0):
        self.cache_dir = cache_dir
        self.delay = delay
        os.makedirs(cache_dir, exist_ok=True)  # Ensure cache directory exists

    def fetch_game_ids(self, start_season, end_season):
        game_ids_all_seasons = []
        season_types = ['Regular Season', 'Pre Season', 'Playoffs']
 
        for season in range(start_season, end_season+1):
            season_str = f'{season}-{str(season+1)[-2:]}'  # Convert season to NBA season format
            cache_file = os.path.join(self.cache_dir, f'game_ids_{season_str}.pkl')

            # Try to load cached data
            if os.path.exists(cache_file):
                with open(cache_file, 'rb') as f:
                    game_ids = pickle.load(f)
                    game_ids_all_seasons.extend(game_ids)
            else:
                game_ids_all_types = []
                for season_type in season_types:
                    log = leaguegamelog.LeagueGameLog(season=season_str, season_type_all_star=season_type)
                    data = log.get_data_frames()[0]
                    game_ids = data['GAME_ID'].unique()
                    game_ids_all_types.extend(game_ids)

                 # Save data to cache
                with open(cache_file, 'wb') as f:
                    pickle.dump(game_ids_all_types, f)

                 # Delay to prevent exceeding rate limit
                time.sleep(self.delay)

                game_ids_all_seasons.extend(game_ids_all_types)

        return game_ids_all_seasons
    

class NBA_FirstScore:
    def __init__(self, game_ids):
        self.game_ids = list(game_ids)
        self.height_cache = {}
        self.results = []

    def convert_height_to_decimal(self, height_str):
        if not height_str or '-' not in height_str:
            return None
        try:
            feet, inches = map(int, height_str.split('-'))
            height_decimal = feet + (inches / 12)
            return height_decimal
        except ValueError:
            return None

    def get_player_height(self, player_id):
        if player_id in self.height_cache:
            return self.height_cache[player_id]
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        player_info_df = player_info.get_data_frames()[0]
        height = player_info_df.iloc[0]['HEIGHT']
        height_decimal = self.convert_height_to_decimal(height)
        self.height_cache[player_id] = height_decimal
        return height_decimal
    

    def get_first_scorer(self,df, team_who_won_ball):
        scoring_events = df[df['HOMEDESCRIPTION'].notnull() | df['VISITORDESCRIPTION'].notnull()]
        for _, row in scoring_events.iterrows():
            description_home = row['HOMEDESCRIPTION']
            description_visitor = row['VISITORDESCRIPTION']
            if isinstance(description_home, str):
                match_home = re.search(r"(\w+.*?) (\(\d PTS\))", description_home)
                if match_home:
                    times = row['PCTIMESTRING']
                    player_name = row['PLAYER1_NAME']
                    team = row['PLAYER1_TEAM_ABBREVIATION']
                    return player_name.replace(' ', '_'), team,times

            if isinstance(description_visitor, str):
                match_visitor = re.search(r"(\w+.*?) (\(\d PTS\))", description_visitor)
                if match_visitor:
                    times = row['PCTIMESTRING']
                    player_name = row['PLAYER1_NAME']
                    team = row['PLAYER1_TEAM_ABBREVIATION']
                    return player_name.replace(' ', '_'), team,times

        return None, None           

    def get_results(self, game_id):
        from nba_api.stats.endpoints import playbyplayv2
        playbyplay_df = playbyplayv2.PlayByPlayV2(game_id=game_id).get_data_frames()[0]
        from nba_api.stats.endpoints import boxscoresummaryv2
        boxscore_summary = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id)
        game_date = pd.Timestamp(boxscore_summary.get_data_frames()[0]['GAME_DATE_EST'].values[0]).strftime('%Y-%m-%d')
        first_quarter_playbyplay = playbyplay_df[playbyplay_df['PERIOD'] == 1]
        jump_balls = playbyplay_df[playbyplay_df['EVENTMSGTYPE'] == 10]
        if playbyplay_df.empty:
            print('Invalid game_id or no data available for this game!')
            return (None, None), (None, None)
        first_jump_ball = jump_balls.iloc[0][
            ['PLAYER1_ID', 'PLAYER3_TEAM_ABBREVIATION', 'PLAYER2_ID', 'PLAYER1_TEAM_ABBREVIATION', 'PLAYER2_TEAM_ABBREVIATION']]
        

        #Extracting starting lineup for that game
        from nba_api.stats.endpoints import boxscoretraditionalv2
        boxscore = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id).get_data_frames()[0]
        # Assume df is your DataFrame
        df = boxscore
        # Filter rows where 'START_POSITION' is not null
        starting_lineup_df = df[df['START_POSITION'].notna()]

        # Get the list of starting players and their positions for each team
        teams = starting_lineup_df['TEAM_ABBREVIATION'].unique()

        home_team = teams[1]
        away_team = teams[0]

        home_team_df = starting_lineup_df[starting_lineup_df['TEAM_ABBREVIATION'] == home_team]
        away_team_df = starting_lineup_df[starting_lineup_df['TEAM_ABBREVIATION'] == away_team]

        home_players = home_team_df['PLAYER_NAME'].tolist()[0:5]
        home_players = [name.replace(' ', '_') for name in home_players]
        home_positions = home_team_df['START_POSITION'].tolist()[0:5]
        home_positions = [name.replace(' ', '_') for name in home_positions]
        away_players = away_team_df['PLAYER_NAME'].tolist()[0:5]
        away_players = [name.replace(' ', '_') for name in away_players]
        away_positions = away_team_df['START_POSITION'].tolist()[0:5]
        away_positions = [name.replace(' ', '_') for name in away_positions]
        if first_jump_ball['PLAYER1_TEAM_ABBREVIATION'] == home_team:
            height1 = self.get_player_height(first_jump_ball['PLAYER1_ID'])
            height2 = self.get_player_height(first_jump_ball['PLAYER2_ID'])
        else:
            height1 = self.get_player_height(first_jump_ball['PLAYER2_ID'])
            height2 = self.get_player_height(first_jump_ball['PLAYER1_ID'])
        height_diff = height1 - height2
        outcome = first_jump_ball['PLAYER3_TEAM_ABBREVIATION']

        return self.get_first_scorer(first_quarter_playbyplay, first_jump_ball['PLAYER3_TEAM_ABBREVIATION']), (game_date,height_diff, outcome),(home_team,away_team,home_players,away_players,home_positions,away_positions)

    def analyze(self):
        cols = ['Player_first_score', 'Team_first_score','Game_time', 'Game_date', 'Height_home_minus_away', 'Team_bounce_winner','Home_team','Away_team','Home_lineup','Away_lineup','Home_positions','Away_positions']
        dates = []
        failed_game_ids = []
        for game_id in tqdm(self.game_ids, desc='Computing outcomes..'):
            try:
                first, jump,other = self.get_results(game_id)
                self.results.append(list(first + jump+ other))
                dates.append(game_id)
            except:
                failed_game_ids.append(game_id)
                pass
        all_data = pd.DataFrame(self.results, columns=cols, index=dates)
        return all_data,failed_game_ids