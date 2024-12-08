import os
import datetime
import sqlite3
import json
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from data.queries import (
    get_point_total,
    audit_df,
    get_races_list,
    get_race_data,
    get_race_years
)

env = Environment(loader=FileSystemLoader('templates'))
db_path = 'race_league_results.db'
CONN = sqlite3.connect(db_path)
CURRENT_YEAR = datetime.datetime.now().year


def create_or_update_standings_data(years, data_dir):
    # Loop through years and create data for user:
    for y in [year for year in years if years > 2023]:
        standings = get_point_total(y, CONN)
        audit = audit_df(y, CONN)
        
        # Convert standings to a dictionary: { "columns": [...], "rows": [[...],[...]] }
        standings_data = {
            "columns": standings.columns.tolist(),
            "rows": standings.values.tolist()
        }

        # Write team standings JSON
        with open(os.path.join(data_dir, f"team_standings_{y}.json"), 'w') as f:
            json.dump(standings_data, f)

        # Save the audit CSV
        audit.to_csv(os.path.join(data_dir, f"race_results_{y}.csv"), index=False)


def create_or_update_race_data(years, data_dir):
    # Get race metadata
    race_list = get_races_list(CONN)
    races_by_year = {}
    for y in years:
        races_for_year = race_list[race_list['year'] == y]
        races_list = races_for_year.to_dict('records')
        races_by_year[y] = races_list

    races_metadata = {
        "years": years,
        "races": races_by_year
    }

    # loop through all the races to get all results! 
    race_results = []
    for year in races_metadata["years"]:
        for race_meta in races_metadata["races"][year]:
            race_results.append(get_race_data(
                'best_time',
                race_meta["race_id"],
                year,
                CONN
            ))
            
    

    with open(os.path.join(data_dir, 'races_metadata.json'), 'w') as f:
        json.dump(races_metadata, f)

    with open(os.path.join(data_dir, 'race_results.json'), 'w') as f:
        json.dump(results_data, f)



def generate_index():
    template = env.get_template('index.html')
    html = template.render(title='Home', current_year=CURRENT_YEAR)
    with open('docs/index.html', 'w') as f:
        f.write(html)


def generate_team_standings_pages(years):
    template = env.get_template('team_standings.html')
    base_url = '../'
    html = template.render(
        years=years,
        base_url=base_url,
        current_year=CURRENT_YEAR
    )

    # Write the generated HTML to docs/team_standings.html
    with open('docs/team_standings.html', 'w') as f:
        f.write(html)


def generate_race_results_page():
    base_url = '../'
    template = env.get_template('race_results.html')
    html = template.render(base_url=base_url, current_year=CURRENT_YEAR)
    with open('docs/race_results.html', 'w') as f:
        f.write(html)


def generate_pages():
    years = get_race_years(CONN)

    # create directory:
    data_dir = 'docs/data'
    os.makedirs('docs/team_standings', exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    # create or update data:
    # create_or_update_standings_data(years, data_dir) # Commented out waiting for 2025 data!
    create_or_update_race_data(years, data_dir)

    # Generate html:
    generate_index()
    #generate_team_standings_pages() # Commented out waiting for 2025 data!
    generate_race_results_page()


if __name__ == '__main__':
    generate_pages()

