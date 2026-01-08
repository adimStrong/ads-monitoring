"""
Database utility functions for BINGO365 Monitoring
"""
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import sys
sys.path.append('..')
from config import DATABASE_URL


def get_engine():
    """Get SQLAlchemy engine"""
    return create_engine(DATABASE_URL)


def get_agents():
    """Get all agents from database"""
    engine = get_engine()
    query = "SELECT id, name FROM agents ORDER BY name"
    return pd.read_sql(query, engine)


def get_agent_performance(agent_id=None, start_date=None, end_date=None):
    """Get performance data for agent(s)"""
    engine = get_engine()

    query = """
        SELECT
            ap.*,
            a.name as agent_name
        FROM ad_performance ap
        JOIN agents a ON ap.agent_id = a.id
        WHERE 1=1
    """
    params = {}

    if agent_id:
        query += " AND ap.agent_id = :agent_id"
        params['agent_id'] = agent_id

    if start_date:
        query += " AND ap.date >= :start_date"
        params['start_date'] = start_date

    if end_date:
        query += " AND ap.date <= :end_date"
        params['end_date'] = end_date

    query += " ORDER BY ap.date DESC, a.name"

    return pd.read_sql(text(query), engine, params=params)


def get_agent_content(agent_id=None, start_date=None, end_date=None):
    """Get content data for agent(s)"""
    engine = get_engine()

    query = """
        SELECT
            ac.*,
            a.name as agent_name
        FROM ad_content ac
        JOIN agents a ON ac.agent_id = a.id
        WHERE 1=1
    """
    params = {}

    if agent_id:
        query += " AND ac.agent_id = :agent_id"
        params['agent_id'] = agent_id

    if start_date:
        query += " AND ac.date >= :start_date"
        params['start_date'] = start_date

    if end_date:
        query += " AND ac.date <= :end_date"
        params['end_date'] = end_date

    query += " ORDER BY ac.date DESC, a.name"

    return pd.read_sql(text(query), engine, params=params)


def get_daily_stats(agent_id=None, start_date=None, end_date=None):
    """Get daily statistics for agent(s)"""
    engine = get_engine()

    query = """
        SELECT
            ds.*,
            a.name as agent_name
        FROM daily_stats ds
        JOIN agents a ON ds.agent_id = a.id
        WHERE 1=1
    """
    params = {}

    if agent_id:
        query += " AND ds.agent_id = :agent_id"
        params['agent_id'] = agent_id

    if start_date:
        query += " AND ds.date >= :start_date"
        params['start_date'] = start_date

    if end_date:
        query += " AND ds.date <= :end_date"
        params['end_date'] = end_date

    query += " ORDER BY ds.date DESC, a.name"

    return pd.read_sql(text(query), engine, params=params)


def get_content_similarity(content_id=None, min_score=0.5):
    """Get content similarity scores"""
    engine = get_engine()

    query = """
        SELECT
            cs.*,
            ac1.primary_content as content_1,
            ac1.date as date_1,
            a1.name as agent_1,
            ac2.primary_content as content_2,
            ac2.date as date_2,
            a2.name as agent_2
        FROM content_similarity cs
        JOIN ad_content ac1 ON cs.content_id_1 = ac1.id
        JOIN ad_content ac2 ON cs.content_id_2 = ac2.id
        JOIN agents a1 ON ac1.agent_id = a1.id
        JOIN agents a2 ON ac2.agent_id = a2.id
        WHERE cs.similarity_score >= :min_score
    """
    params = {'min_score': min_score}

    if content_id:
        query += " AND (cs.content_id_1 = :content_id OR cs.content_id_2 = :content_id)"
        params['content_id'] = content_id

    query += " ORDER BY cs.similarity_score DESC"

    return pd.read_sql(text(query), engine, params=params)


def get_team_summary(start_date=None, end_date=None):
    """Get team summary statistics"""
    engine = get_engine()

    query = """
        SELECT
            a.name as agent_name,
            COUNT(DISTINCT ap.date) as days_active,
            COALESCE(SUM(ap.total_ad), 0) as total_ads,
            COALESCE(SUM(ap.impressions), 0) as total_impressions,
            COALESCE(SUM(ap.clicks), 0) as total_clicks,
            COALESCE(AVG(ap.ctr_percent), 0) as avg_ctr,
            COALESCE(AVG(ap.conversion_rate), 0) as avg_conversion,
            COALESCE(SUM(ap.active_count), 0) as total_active
        FROM agents a
        LEFT JOIN ad_performance ap ON a.id = ap.agent_id
    """
    params = {}

    if start_date:
        query += " AND ap.date >= :start_date"
        params['start_date'] = start_date

    if end_date:
        query += " AND ap.date <= :end_date"
        params['end_date'] = end_date

    query += " GROUP BY a.id, a.name ORDER BY a.name"

    return pd.read_sql(text(query), engine, params=params)


def get_content_summary(agent_id=None, start_date=None, end_date=None):
    """Get content summary for agents"""
    engine = get_engine()

    query = """
        SELECT
            a.name as agent_name,
            COUNT(*) as total_posts,
            COUNT(DISTINCT ac.content_hash) as unique_posts,
            COUNT(*) - COUNT(DISTINCT ac.content_hash) as recycled_posts,
            ROUND(COUNT(DISTINCT ac.content_hash)::numeric / NULLIF(COUNT(*), 0) * 100, 1) as freshness_pct
        FROM agents a
        LEFT JOIN ad_content ac ON a.id = ac.agent_id
        WHERE 1=1
    """
    params = {}

    if agent_id:
        query += " AND a.id = :agent_id"
        params['agent_id'] = agent_id

    if start_date:
        query += " AND ac.date >= :start_date"
        params['start_date'] = start_date

    if end_date:
        query += " AND ac.date <= :end_date"
        params['end_date'] = end_date

    query += " GROUP BY a.id, a.name ORDER BY a.name"

    return pd.read_sql(text(query), engine, params=params)
