import os
import datetime
import sqlite3
import json
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from data.queries import get_point_total, audit_df

env = Environment(loader=FileSystemLoader('templates'))
db_path = 'race_league_results.db'
CONN = sqlite3.connect(db_path)
CURRENT_YEAR = datetime.datetime.now().year


def get_available_years():
    # Query the available years from your Races table
    df = pd.read_sql("SELECT strftime('%Y', race_date) as year FROM Races where race_date > '2024-01-01' group by 1", conn)
    return df['year'].tolist()


def generate_team_standings_pages():
    years = get_available_years()
    os.makedirs('docs/team_standings', exist_ok=True)
    data_dir = 'docs/data'
    os.makedirs(data_dir, exist_ok=True)
    template = env.get_template('team_standings.html')
    base_url = '../'

    # Loop through years and create data for user:
    for y in years:
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

    html = template.render(
        years=years,
        base_url=base_url,
        current_year=CURRENT_YEAR
    )

    # Write the generated HTML to docs/team_standings.html
    with open('docs/team_standings.html', 'w') as f:
        f.write(html)


def generate_index():
    template = env.get_template('index.html')
    html = template.render(title='Home', current_year=CURRENT_YEAR)
    with open('docs/index.html', 'w') as f:
        f.write(html)

def generate_pages():
    generate_index()
    # Until we have actual 2025 data, lets keep the team standings page as is!
    #generate_team_standings_pages()

if __name__ == '__main__':
    generate_pages()
