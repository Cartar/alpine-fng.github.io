import os
import datetime
import sqlite3
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from data.queries import get_point_total, audit_df

env = Environment(loader=FileSystemLoader('templates'))
db_path = 'race_league_results.db'
CONN = sqlite3.connect(db_path)
current_year = datetime.datetime.now().year


def get_available_years():
    # Query the available years from your Races table
    #query = "SELECT year FROM Races GROUP BY year ORDER BY year DESC"
    #df = pd.read_sql(query, conn)
    return [2024]#df['year'].tolist()


def generate_team_standings_pages():
    years = get_available_years()
    os.makedirs('docs/team_standings', exist_ok=True)
    template = env.get_template('team_standings.html')

    # We assume the site is hosted with docs/ as the root
    # If your structure differs, adjust base_url accordingly.
    base_url = '../'

    for y in years:
        standings = get_point_total(y, CONN)
        audit = audit_df(y, CONN)
        
        # Save the audit CSV
        audit.to_csv(f'docs/team_standings/audit_{y}.csv', index=False)

        # Convert df to lists for Jinja iteration
        cols = standings.columns.tolist()
        rows = standings.values.tolist()

        html = template.render(
            title=f"Team Standings {y}",
            year=y,
            years=years,
            cols=cols,
            rows=rows,
            base_url=base_url,
            current_year=current_year
        )

        # Write the HTML file for this year
        with open(f'docs/team_standings/{y}.html', 'w') as f:
            f.write(html)


def generate_index():
    template = env.get_template('index.html')
    html = template.render(title='Home', current_year=current_year)
    with open('docs/index.html', 'w') as f:
        f.write(html)

def generate_pages():
    generate_index()
    generate_team_standings_pages()

if __name__ == '__main__':
    generate_pages()
