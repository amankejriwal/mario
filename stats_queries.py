"""
Analytics queries for the Mario Genie App stats dashboard.
Provides insights into user behavior, engagement, and feedback.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from event_logger import get_db_connection

logger = logging.getLogger(__name__)


def get_unique_visitors(period: str = 'daily') -> Dict[str, Any]:
    """
    Get unique visitor counts for different time periods.
    
    Args:
        period: 'daily', 'weekly', 'monthly', or 'quarterly'
    
    Returns:
        Dict with period data and counts
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if period == 'daily':
                    query = """
                        SELECT 
                            DATE(timestamp) as date,
                            COUNT(DISTINCT user_id) as unique_visitors
                        FROM user_events
                        WHERE event_type = 'page_visit'
                          AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY DATE(timestamp)
                        ORDER BY date DESC
                    """
                elif period == 'weekly':
                    query = """
                        SELECT 
                            DATE_TRUNC('week', timestamp) as week,
                            COUNT(DISTINCT user_id) as unique_visitors
                        FROM user_events
                        WHERE event_type = 'page_visit'
                          AND timestamp >= CURRENT_DATE - INTERVAL '12 weeks'
                        GROUP BY DATE_TRUNC('week', timestamp)
                        ORDER BY week DESC
                    """
                elif period == 'monthly':
                    query = """
                        SELECT 
                            DATE_TRUNC('month', timestamp) as month,
                            COUNT(DISTINCT user_id) as unique_visitors
                        FROM user_events
                        WHERE event_type = 'page_visit'
                          AND timestamp >= CURRENT_DATE - INTERVAL '12 months'
                        GROUP BY DATE_TRUNC('month', timestamp)
                        ORDER BY month DESC
                    """
                else:  # quarterly
                    query = """
                        SELECT 
                            DATE_TRUNC('quarter', timestamp) as quarter,
                            COUNT(DISTINCT user_id) as unique_visitors
                        FROM user_events
                        WHERE event_type = 'page_visit'
                          AND timestamp >= CURRENT_DATE - INTERVAL '2 years'
                        GROUP BY DATE_TRUNC('quarter', timestamp)
                        ORDER BY quarter DESC
                    """
                
                cur.execute(query)
                results = cur.fetchall()
                return {
                    'period': period,
                    'data': [{'date': str(row[0]), 'count': row[1]} for row in results]
                }
    except Exception as e:
        logger.error(f"Error fetching unique visitors: {e}")
        return {'period': period, 'data': []}


def get_nps_score() -> Dict[str, Any]:
    """
    Calculate Net Promoter Score based on user feedback.
    NPS = (% Promoters) - (% Detractors)
    Promoters = positive feedback, Detractors = negative feedback
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) FILTER (WHERE feedback_type = 'positive') as promoters,
                        COUNT(*) FILTER (WHERE feedback_type = 'negative') as detractors,
                        COUNT(*) as total
                    FROM user_events
                    WHERE event_type = 'feedback'
                """)
                row = cur.fetchone()
                promoters, detractors, total = row[0] or 0, row[1] or 0, row[2] or 0
                
                if total == 0:
                    return {'nps': 0, 'promoters': 0, 'detractors': 0, 'total': 0}
                
                nps = ((promoters - detractors) / total) * 100
                return {
                    'nps': round(nps, 1),
                    'promoters': promoters,
                    'detractors': detractors,
                    'total': total,
                    'promoter_percentage': round((promoters / total) * 100, 1),
                    'detractor_percentage': round((detractors / total) * 100, 1)
                }
    except Exception as e:
        logger.error(f"Error calculating NPS: {e}")
        return {'nps': 0, 'promoters': 0, 'detractors': 0, 'total': 0}


def get_top_users(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top users by activity (conversations + messages)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        user_id,
                        user_email,
                        COUNT(*) FILTER (WHERE event_type = 'start_conversation') as conversations,
                        COUNT(*) FILTER (WHERE event_type = 'send_message') as messages,
                        COUNT(*) FILTER (WHERE event_type = 'feedback' AND feedback_type = 'positive') as positive_feedback,
                        COUNT(*) FILTER (WHERE event_type = 'feedback' AND feedback_type = 'negative') as negative_feedback,
                        COUNT(*) as total_events
                    FROM user_events
                    WHERE event_type IN ('start_conversation', 'send_message', 'feedback')
                    GROUP BY user_id, user_email
                    ORDER BY total_events DESC
                    LIMIT %s
                """, (limit,))
                
                results = cur.fetchall()
                return [{
                    'user_id': row[0],
                    'user_email': row[1] or row[0],
                    'conversations': row[2],
                    'messages': row[3],
                    'positive_feedback': row[4],
                    'negative_feedback': row[5],
                    'total_activity': row[6]
                } for row in results]
    except Exception as e:
        logger.error(f"Error fetching top users: {e}")
        return []


def get_engagement_metrics() -> Dict[str, Any]:
    """Get overall engagement metrics"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(DISTINCT user_id) FILTER (WHERE event_type = 'page_visit') as total_users,
                        COUNT(*) FILTER (WHERE event_type = 'start_conversation') as total_conversations,
                        COUNT(*) FILTER (WHERE event_type = 'send_message') as total_messages,
                        COUNT(*) FILTER (WHERE event_type = 'feedback') as total_feedback
                    FROM user_events
                """)
                row = cur.fetchone()
                
                return {
                    'total_users': row[0] or 0,
                    'total_conversations': row[1] or 0,
                    'total_messages': row[2] or 0,
                    'total_feedback': row[3] or 0,
                    'avg_messages_per_conversation': round((row[2] or 0) / (row[1] or 1), 2)
                }
    except Exception as e:
        logger.error(f"Error fetching engagement metrics: {e}")
        return {}


def get_activity_by_hour() -> List[Dict[str, Any]]:
    """Get activity distribution by hour of day"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        EXTRACT(HOUR FROM timestamp) as hour,
                        COUNT(*) as activity_count
                    FROM user_events
                    WHERE event_type IN ('start_conversation', 'send_message')
                    GROUP BY EXTRACT(HOUR FROM timestamp)
                    ORDER BY hour
                """)
                
                results = cur.fetchall()
                return [{'hour': int(row[0]), 'count': row[1]} for row in results]
    except Exception as e:
        logger.error(f"Error fetching hourly activity: {e}")
        return []


def get_conversation_metrics() -> Dict[str, Any]:
    """Get conversation-level metrics"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    WITH conversation_stats AS (
                        SELECT 
                            conversation_id,
                            COUNT(*) FILTER (WHERE event_type = 'send_message') as message_count,
                            COUNT(*) FILTER (WHERE event_type = 'feedback') as has_feedback
                        FROM user_events
                        WHERE conversation_id IS NOT NULL
                        GROUP BY conversation_id
                    )
                    SELECT 
                        COUNT(*) as total_conversations,
                        AVG(message_count) as avg_messages,
                        COUNT(*) FILTER (WHERE has_feedback > 0) as conversations_with_feedback,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY message_count) as median_messages
                    FROM conversation_stats
                """)
                row = cur.fetchone()
                
                total = row[0] or 0
                return {
                    'total_conversations': total,
                    'avg_messages_per_conversation': round(row[1] or 0, 2),
                    'conversations_with_feedback': row[2] or 0,
                    'feedback_rate': round(((row[2] or 0) / total * 100) if total > 0 else 0, 1),
                    'median_messages': float(row[3] or 0)
                }
    except Exception as e:
        logger.error(f"Error fetching conversation metrics: {e}")
        return {}


def get_user_retention() -> List[Dict[str, Any]]:
    """Calculate user retention over time"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    WITH user_cohorts AS (
                        SELECT 
                            user_id,
                            DATE_TRUNC('week', MIN(timestamp)) as cohort_week
                        FROM user_events
                        WHERE event_type = 'page_visit'
                        GROUP BY user_id
                    ),
                    user_activity AS (
                        SELECT 
                            uc.user_id,
                            uc.cohort_week,
                            DATE_TRUNC('week', ue.timestamp) as activity_week
                        FROM user_cohorts uc
                        JOIN user_events ue ON uc.user_id = ue.user_id
                        WHERE ue.event_type = 'page_visit'
                    )
                    SELECT 
                        cohort_week,
                        COUNT(DISTINCT user_id) as cohort_size,
                        COUNT(DISTINCT CASE WHEN activity_week > cohort_week THEN user_id END) as retained_users
                    FROM user_activity
                    WHERE cohort_week >= CURRENT_DATE - INTERVAL '12 weeks'
                    GROUP BY cohort_week
                    ORDER BY cohort_week DESC
                """)
                
                results = cur.fetchall()
                return [{
                    'cohort_week': str(row[0]),
                    'cohort_size': row[1],
                    'retained_users': row[2],
                    'retention_rate': round((row[2] / row[1] * 100) if row[1] > 0 else 0, 1)
                } for row in results]
    except Exception as e:
        logger.error(f"Error calculating retention: {e}")
        return []


def get_feedback_over_time() -> List[Dict[str, Any]]:
    """Get feedback trends over time"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        DATE(timestamp) as date,
                        COUNT(*) FILTER (WHERE feedback_type = 'positive') as positive,
                        COUNT(*) FILTER (WHERE feedback_type = 'negative') as negative
                    FROM user_events
                    WHERE event_type = 'feedback'
                      AND timestamp >= CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                """)
                
                results = cur.fetchall()
                return [{
                    'date': str(row[0]),
                    'positive': row[1],
                    'negative': row[2]
                } for row in results]
    except Exception as e:
        logger.error(f"Error fetching feedback trends: {e}")
        return []


def get_popular_questions() -> List[Dict[str, Any]]:
    """Get most common questions (from metadata)"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        metadata->>'question' as question,
                        COUNT(*) as count
                    FROM user_events
                    WHERE event_type = 'start_conversation'
                      AND metadata IS NOT NULL
                      AND metadata->>'question' IS NOT NULL
                    GROUP BY metadata->>'question'
                    ORDER BY count DESC
                    LIMIT 20
                """)
                
                results = cur.fetchall()
                return [{
                    'question': row[0],
                    'count': row[1]
                } for row in results if row[0]]
    except Exception as e:
        logger.error(f"Error fetching popular questions: {e}")
        return []
