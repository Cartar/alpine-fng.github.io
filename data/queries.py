import pandas as pd


def get_race_years(conn):
    # Used to use: `strftime('%Y', race_date) as year`; but switched to description for easy of use...
    df = pd.read_sql("""
        SELECT substr(description, 1,4) as year
        FROM Races
        GROUP BY 1
        ORDER BY CAST(year AS INT) DESC
        """,
        conn
    )
    return df['year'].tolist()


def get_race_data(order_by, race_id, year, conn):
    # Uses a left join for the default racer points
    sql = f"""
    SELECT 
        CASE
            WHEN team.bib is NOT NULL THEN team.bib
            ELSE race.bib
        END AS bib
        ,
        CASE
            WHEN team.name is NOT NULL THEN team.name
            WHEN names.name is NOT NULL THEN names.name
            ELSE race.racer_id
        END AS name,
        race.racer_id,
        race.discipline,
        team,
        tier,
        run1,
        run2,
        best_time,
        points
    FROM (
        select racer_id, discipline, team, tier, run1, run2, best_time, points, bib
        from RaceResults
        where race_id = {race_id}
    ) AS race 
    LEFT JOIN (
        select bib, discipline, racer_id, name
        from Teams
        where year = {year}
    ) AS team
    ON race.racer_id = team.racer_id
    AND race.discipline = team.discipline
    LEFT JOIN (
        SELECT racer_id, CONCAT(first_name, ' ', last_name) AS name
        from Racers
    ) AS names
    ON race.racer_id = names.racer_id
    ORDER BY {order_by};
    """
    
    return pd.read_sql_query(sql, conn)


def _points_sql_base(year):
    return f"""
        WITH ranked AS (
            SELECT 
                rr.team,
                rr.racer_id,
                rr.discipline,
                rr.tier,
                rr.points,
                ROW_NUMBER() OVER (
                    PARTITION BY rr.team, rr.racer_id, rr.discipline, rr.tier
                    ORDER BY rr.points DESC
                ) AS rn
            FROM RaceResults rr
            JOIN Races r ON rr.race_id = r.race_id
            WHERE substr(r.description, 1,4) = '{year}'
            and lower(description) not like '%time%' and lower(description) not like '%trial%'
        )
        , top3 AS (
            SELECT
                team,
                racer_id,
                discipline,
                tier,
                SUM(points) AS total_top_3_points
            FROM ranked
            WHERE rn <= 3
            GROUP BY team, racer_id, discipline, tier
        )
    """

def get_point_total(year, conn):
    # Only take top points per top racer's top_3_points
    sql = _points_sql_base(year) + f"""
    , top3_filtered AS (
            SELECT
                team,
                discipline,
                tier,
                Max(total_top_3_points) AS best_total_top_3_points
            FROM top3
            GROUP BY team, discipline, tier
        )

    SELECT
        team,
        SUM(best_total_top_3_points) AS team_points
    FROM top3_filtered
    GROUP BY team
    ORDER BY team_points DESC;
    """
    
    return pd.read_sql_query(sql, conn)


def get_table_schema(tablename, conn):
    cursor = conn.execute(f"PRAGMA table_info({tablename});")
    return cursor.fetchall()


def get_races_list(conn):
    """
    Unlike other queries from Races, we want to include time trails here
    to display them in the website.
    """
    return pd.read_sql_query(
        "select *, substr(description, 1,4) as year From Races order by race_date DESC"
        , conn
    )


def audit_df(year, conn):
    # get all race IDs from a given year:
    ids = pd.read_sql_query(
        f"select * From Races where substr(description, 1,4) = '{year}' and lower(description) not like '%time%' and lower(description) not like '%trial%' order by race_date ASC",
        conn
    )

    # gather all race data
    order_by='team, tier'
    join_keys = ["team", "tier", "racer_id"]
    cols_to_keep = ["run1", "run2", "best_time", "points"]

    for i, race_id in enumerate(list(ids.race_id)):
        race = get_race_data(order_by, race_id, year, conn)
        
        if i == 0:
            # First race is the base of our audit
            audit_df = race
        
        else:
            audit_df = audit_df.merge(
                race[cols_to_keep + join_keys],
                how = "inner",
                on=join_keys
            )
        
        # rename the columns:
        n = i+1 # race number
        cols = {col: f"{col}_race{n}" for col in cols_to_keep}
        audit_df.rename(columns=cols, inplace=True)

    # for any NULL names, put avg tier points:
    audit_df['name'] = audit_df['name'].fillna('Average Tier Points')

    # gather top 3 points:
    sql = _points_sql_base(year) + "SELECT * FROM top3"
    top_points = pd.read_sql_query(sql, conn)

    # Join and return results:    
    return audit_df.merge(
        top_points[join_keys + ["total_top_3_points"]],
        how="inner",
        on=join_keys
    ).drop(columns=["racer_id"])
