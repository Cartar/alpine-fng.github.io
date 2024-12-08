import pandas as pd


def get_race_data(order_by, race_id, year, conn):
    # Uses a left join for the default racer points
    sql = f"""
    SELECT 
        bib, name, race.discipline, team, tier, run1, run2, best_time, points
    FROM (
        select racer_id, discipline, team, tier, run1, run2, best_time, points
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
    ORDER BY {order_by}
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
            WHERE strftime('%Y', r.race_date) = '{year}'
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
    sql = _points_sql_base(year) + f"""
    SELECT
        team,
        SUM(total_top_3_points) AS team_points
    FROM top3
    GROUP BY team
    ORDER BY team_points DESC;
    """
    
    return pd.read_sql_query(sql, conn)


def get_table_schema(tablename, conn):
    cursor = conn.execute(f"PRAGMA table_info({tablename});")
    return cursor.fetchall()


def get_races_list(conn):
    return pd.read_sql_query("select * From Races order by race_date DESC", conn)


def audit_df(year, conn):
    # get all race IDs from a given year:
    ids = pd.read_sql_query(
        f"select race_id From Races where strftime('%Y', race_date) = '{year}' order by race_date ASC",
        conn
    )

    # gather all race data
    order_by='team, tier'
    join_keys = ["team", "tier"]
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
    )


    