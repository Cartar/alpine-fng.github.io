import re 
import pandas as pd
import numpy as np

RACE_RESULT_COL_ORDER = ["racer_id", "discipline", "team", "tier", "run1", "run2", "best_time", "points", "race_id", "bib"]


def load_clean_results(path, startList, race_id=None, max_points=10):
    assert race_id is not None, "failed to provide a race ID"
        
    join_keys = ["bib", "racer_id"]
    result_cols = ["bib", "racer_id", "run1", "run2"]
    
    results = pd.read_csv(path, header=None, names=result_cols)
    results["racer_id"] = results["racer_id"].apply(clean_string)

    combined = startList.merge(results, how="left", on=join_keys)
    _, points = calculate_points(combined, top_points=max_points)

    points.loc[points.racer_id.isnull(), 'racer_id'] = 'avg_tier_points'
    points["race_id"]=race_id

    # add anyone not on a team:
    results_no_team = results[~results['racer_id'].isin(points['racer_id'])]
    results_no_team =  get_best_time(results_no_team)
    results_no_team = results_no_team[results_no_team.best_time < 9998]

    # Append the new results to the points dataframe
    points = pd.concat([points, results_no_team], ignore_index=True)

    return points[RACE_RESULT_COL_ORDER]


def upload_results(results, race_id, race_date, description, conn):
    # Create race data:
    race_data = {
        'race_id': [race_id],
        'race_date': [race_date],
        'description': [description]
    }
    race_upload = pd.DataFrame(race_data)
    race_upload['race_date'] = pd.to_datetime(race_upload['race_date'], format='%m/%d/%Y')

    # Check that the race ID isn't already in Races and RaceResults before upload:
    if pd.read_sql_query(f"SELECT * FROM Races where race_id = {race_id}", conn).shape[0] == 0:
        race_upload.to_sql('Races', conn, if_exists='append', index=False)
    if pd.read_sql_query(f"SELECT * FROM RaceResults where race_id = {race_id}", conn).shape[0] == 0:
        results.to_sql('RaceResults', conn, if_exists='append', index=False)
    
    conn.commit()


def prep_race_results(
    path,
    #race_date,
    race_id,
    #description,
    year,
    #N_tiers,
    #N_teams,
    max_points,
    conn
):
    #assert len(race_date.split("/")) == 3, "race date wrong format"
    #assert len(race_date) == 10, "race date wrong format"
    #year = race_date[-4:]

    # Get start list
    sql = f"""
        select bib, discipline, racer_id, tier, team
        from Teams
        where year = {year}
        and is_active = TRUE
    """
    startList = pd.read_sql_query(sql, conn)

    # get results:
    results = load_clean_results(path, startList, race_id, max_points)
        
    ## Assert results have the right dims:
    ## removed this because we now have 9 racers in on tier 11...
    #N_cols = 10 # As of 2025, now we upload bib as well!
    #for i in range (N_tiers, 0, -1):
    #    assert results[results.tier == i].sort_values(["tier", 'points'], ascending=False).shape == (N_teams, N_cols), f"results are the wrong dims: {results[results.tier == i].sort_values(['tier', 'points'], ascending=False).shape} != {(N_teams, N_cols)}"

    return results


def drop_nulls(df, col):
    return df.dropna(subset=[col])


def clean_string(s):
    """
    Removes whitespace and non-alphanumeric characters from a string.
    
    Parameters:
    s (str): The input string to clean.

    Returns:
    str: A cleaned string with only alphanumeric characters.
    """
    if isinstance(s, str):
        return re.sub(r'\W+', '', s).lower()  # Removes non-alphanumeric characters and whitespace
    else:
        return ''  # Handle non-string cases, e.g., None or NaN


def get_best_time(df):
    df.replace({'DNF': 9998,"DSQ": 9998, "DNS": 9999, pd.NA: 9999}, inplace=True)
    df['run1'] = pd.to_numeric(df['run1']) # errors='coerce')
    df['run2'] = pd.to_numeric(df['run2']) # errors='coerce')
    df['best_time'] = df[['run1', 'run2']].min(axis=1)
    return df


def calculate_points(df, top_points):
    df =  get_best_time(df)
    # Initialize a column for points
    df['points'] = 0
    
    # Process each tier
    for tier in df['tier'].unique():
        # Filter the tier
        tier_df = df[df['tier'] == tier]
    
        # Sort by best_time
        tier_sorted = tier_df.sort_values(by='best_time')

        # Assign points based on the number of racers in the tier
        num_racers = len(tier_sorted)
        tier_sorted['points'] = range(top_points, top_points - num_racers, -1)
    
        # Handle ties for racers with the same best_time
        tie_groups = tier_sorted.groupby('best_time')
        for best_time, group in tie_groups:
            if len(group) > 1:  # Check for ties
                tie_indices = group.index
                # Average the points of the tied positions
                tied_points = tier_sorted.loc[tie_indices, 'points'].mean()
                tier_sorted.loc[tie_indices, 'points'] = tied_points

        # Set absent racer points to zero:
        tier_sorted.loc[tier_sorted['best_time'] == 9999, 'points'] = 0
        
        # Handle ties for DNF (split points for racers with 9998 as their best_time)
        dnf_racers = tier_sorted[tier_sorted['best_time'] == 9998]
        if not dnf_racers.empty:
            dnf_points = dnf_racers['points'].sum() / len(dnf_racers)
            tier_sorted.loc[tier_sorted['best_time'] == 9998, 'points'] = dnf_points
    
        # Update the main dataframe
        df.loc[df['tier'] == tier, 'points'] = tier_sorted['points']

    # Calculate team points
    teams = df['team'].unique()
    team_dfs = []
    team_points = {}
    for team in teams:
        team_df = df[df['team'] == team]
        # If a team is missing a racer in a tier, give them the average points of that tier
        for tier in df['tier'].unique():
            if tier not in team_df['tier'].values:
                # Get tier average:
                tier_df = df[df['tier'] == tier]
                num_racers = len(tier_df)
                avg_points = (top_points + (top_points - (num_racers-1))) / 2
                ## Old way of adding avg points:
                #team_df.loc[-1] = [pd.NA, pd.NA, pd.NA, tier, team, pd.NA, pd.NA, pd.NA, avg_points]
                #team_df.reset_index(drop=True, inplace=True)
                # Add a row for the missing tier with average points
                missing_row = {
                    'best_time': pd.NA,
                    'points': avg_points,
                    'tier': tier,
                    'team': team,
                }
                # Add additional columns to maintain the dataframe structure
                for col in [col for col in df.columns if col not in missing_row]:
                    missing_row[col] = pd.NA
                team_df = pd.concat([team_df, pd.DataFrame([missing_row])], ignore_index=True)

        team_points[team] = team_df['points'].sum()
        team_dfs.append(team_df)
    
    df_out = pd.concat(team_dfs)
    
    return team_points, df_out
    