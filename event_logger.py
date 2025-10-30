"""
Event logging module for tracking user interactions with Mario Genie App.
Stores events in PostgreSQL for analytics and user attribution.
"""

import os
import logging
import psycopg2
from psycopg2.extras import Json, RealDictCursor
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Database connection parameters
# Note: Databricks Lakehouse PostgreSQL uses OAuth token as password
DB_HOST = os.getenv("DB_HOST", "instance-debc5f01-b417-48cc-9946-644617771b6f.database.azuredatabricks.net")
DB_NAME = os.getenv("DB_NAME", "databricks_postgres")
DB_USER = os.getenv("DB_USER", "kejria01@heiway.net")
DB_PASSWORD = os.getenv("DB_PASSWORD")  # OAuth token for Lakehouse PostgreSQL
DB_PORT = os.getenv("DB_PORT", "5432")

def get_oauth_token():
    """Get OAuth token for Databricks Lakehouse PostgreSQL"""
    # If DB_PASSWORD is set, use it (it's the OAuth token)
    if DB_PASSWORD:
        logger.debug("Using OAuth token from DB_PASSWORD environment variable")
        return DB_PASSWORD
    
    # Try to get token from Databricks SDK
    try:
        from databricks.sdk import WorkspaceClient
        ws = WorkspaceClient()
        
        # Check various token sources in the SDK config
        if hasattr(ws.config, 'token') and ws.config.token:
            logger.debug("Using OAuth token from WorkspaceClient.config.token")
            return ws.config.token
        
        # Try to get token from auth object
        if hasattr(ws.config, 'authenticate'):
            try:
                auth_headers = ws.config.authenticate()
                if 'Authorization' in auth_headers:
                    token = auth_headers['Authorization'].replace('Bearer ', '')
                    logger.debug("Extracted OAuth token from authentication headers")
                    return token
            except Exception as auth_err:
                logger.debug(f"Could not extract token from authenticate(): {auth_err}")
        
        # Try api_client token
        if hasattr(ws, 'api_client') and hasattr(ws.api_client, 'token'):
            logger.debug("Using OAuth token from api_client.token")
            return ws.api_client.token
            
    except Exception as e:
        logger.warning(f"Could not get OAuth token from SDK: {e}")
    
    raise ValueError("No OAuth token available for database connection. Please set DB_PASSWORD environment variable or configure Databricks authentication.")


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        # Get OAuth token for Lakehouse PostgreSQL
        oauth_token = get_oauth_token()
        
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=oauth_token,  # OAuth token used as password
            port=DB_PORT,
            sslmode='require'
        )
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def log_event(
    event_type: str,
    user_id: str,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
    conversation_id: Optional[str] = None,
    message_id: Optional[str] = None,
    feedback_type: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Log a user event to the database.
    Gracefully fails if database is unavailable - won't crash the app.
    
    Args:
        event_type: Type of event ('page_visit', 'start_conversation', 'send_message', 'feedback')
        user_id: Unique identifier for the user
        user_email: User's email address
        user_name: User's display name
        conversation_id: Genie conversation ID
        message_id: Genie message ID
        feedback_type: 'positive' or 'negative' for feedback events
        session_id: Session identifier for grouping user interactions
        metadata: Additional context data (stored as JSONB)
    
    Returns:
        bool: True if event was logged successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_events (
                        event_type, user_id, user_email, user_name,
                        conversation_id, message_id, feedback_type,
                        session_id, metadata, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    event_type,
                    user_id,
                    user_email,
                    user_name,
                    conversation_id,
                    message_id,
                    feedback_type,
                    session_id,
                    Json(metadata) if metadata else None,
                    datetime.utcnow()
                ))
        logger.debug(f"✅ Logged {event_type} event for user {user_id}")
        return True
    except ValueError as ve:
        # OAuth token not available - log as debug, not error
        logger.debug(f"Event logging unavailable (no DB credentials): {ve}")
        return False
    except Exception as e:
        # Other database errors - log as warning
        logger.warning(f"Failed to log {event_type} event: {e}")
        return False


def log_page_visit(user_id: str, user_email: Optional[str] = None, 
                   user_name: Optional[str] = None, session_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Log a page visit event"""
    return log_event(
        event_type='page_visit',
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        session_id=session_id,
        metadata=metadata
    )


def log_start_conversation(
    user_id: str,
    conversation_id: str,
    message_id: str,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
    session_id: Optional[str] = None,
    question: Optional[str] = None
) -> bool:
    """Log a start conversation event"""
    metadata = {"question": question} if question else None
    return log_event(
        event_type='start_conversation',
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        conversation_id=conversation_id,
        message_id=message_id,
        session_id=session_id,
        metadata=metadata
    )


def log_send_message(
    user_id: str,
    conversation_id: str,
    message_id: str,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
    session_id: Optional[str] = None,
    message: Optional[str] = None
) -> bool:
    """Log a send message event"""
    metadata = {"message": message} if message else None
    return log_event(
        event_type='send_message',
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        conversation_id=conversation_id,
        message_id=message_id,
        session_id=session_id,
        metadata=metadata
    )


def log_sql_response(
    user_id: str,
    conversation_id: str,
    message_id: str,
    question: str,
    sql_query: str,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
    session_id: Optional[str] = None
) -> bool:
    """Log SQL query returned by Genie API"""
    metadata = {
        "question": question,
        "sql_query": sql_query
    }
    return log_event(
        event_type='sql_response',
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        conversation_id=conversation_id,
        message_id=message_id,
        session_id=session_id,
        metadata=metadata
    )


def log_feedback(
    user_id: str,
    conversation_id: str,
    message_id: str,
    feedback_type: str,  # 'positive' or 'negative'
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
    session_id: Optional[str] = None
) -> bool:
    """
    Log a feedback event (thumbs up/down) using UPSERT logic.
    If feedback exists for this user+conversation+message, update it.
    If switching to positive, clear any comment.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check if feedback already exists
                cur.execute("""
                    SELECT event_id FROM user_events
                    WHERE user_id = %s
                      AND conversation_id = %s
                      AND message_id = %s
                      AND event_type = 'feedback'
                    LIMIT 1
                """, (user_id, conversation_id, message_id))
                
                existing = cur.fetchone()
                
                if existing:
                    # Update existing feedback
                    # Clear comment if switching to positive
                    if feedback_type == 'positive':
                        cur.execute("""
                            UPDATE user_events
                            SET feedback_type = %s,
                                timestamp = %s,
                                comment = NULL
                            WHERE user_id = %s
                              AND conversation_id = %s
                              AND message_id = %s
                              AND event_type = 'feedback'
                        """, (
                            feedback_type,
                            datetime.utcnow(),
                            user_id,
                            conversation_id,
                            message_id
                        ))
                    else:
                        # Keep existing comment for negative feedback
                        cur.execute("""
                            UPDATE user_events
                            SET feedback_type = %s,
                                timestamp = %s
                            WHERE user_id = %s
                              AND conversation_id = %s
                              AND message_id = %s
                              AND event_type = 'feedback'
                        """, (
                            feedback_type,
                            datetime.utcnow(),
                            user_id,
                            conversation_id,
                            message_id
                        ))
                    logger.debug(f"✅ Updated feedback to {feedback_type} for message {message_id}")
                else:
                    # Insert new feedback
                    cur.execute("""
                        INSERT INTO user_events (
                            event_type, user_id, user_email, user_name,
                            conversation_id, message_id, feedback_type,
                            session_id, timestamp
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        'feedback',
                        user_id,
                        user_email,
                        user_name,
                        conversation_id,
                        message_id,
                        feedback_type,
                        session_id,
                        datetime.utcnow()
                    ))
                    logger.debug(f"✅ Inserted new {feedback_type} feedback for message {message_id}")
                
        return True
    except ValueError as ve:
        logger.debug(f"Feedback logging unavailable (no DB credentials): {ve}")
        return False
    except Exception as e:
        logger.warning(f"Failed to log feedback: {e}")
        return False


def save_comment(
    user_id: str,
    conversation_id: str,
    message_id: str,
    comment: str
) -> bool:
    """
    Save a user comment for a feedback event.
    Updates the most recent negative feedback event for this message.
    
    Args:
        user_id: User identifier
        conversation_id: Conversation ID
        message_id: Message ID
        comment: User's comment text
    
    Returns:
        bool: True if comment was saved successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Update the most recent negative feedback event for this message
                cur.execute("""
                    UPDATE user_events
                    SET comment = %s
                    WHERE event_id = (
                        SELECT event_id
                        FROM user_events
                        WHERE user_id = %s
                          AND conversation_id = %s
                          AND message_id = %s
                          AND event_type = 'feedback'
                          AND feedback_type = 'negative'
                        ORDER BY timestamp DESC
                        LIMIT 1
                    )
                """, (
                    comment,
                    user_id,
                    conversation_id,
                    message_id
                ))
                
                if cur.rowcount > 0:
                    logger.debug(f"✅ Saved comment for message {message_id}")
                    return True
                else:
                    logger.warning(f"No negative feedback event found to attach comment for message {message_id}")
                    return False
    except ValueError as ve:
        logger.debug(f"Comment save unavailable (no DB credentials): {ve}")
        return False
    except Exception as e:
        logger.warning(f"Failed to save comment: {e}")
        return False


def update_session(
    session_id: str,
    user_id: str,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None
) -> bool:
    """
    Update or create a user session record.
    Updates last_activity timestamp on each call.
    Gracefully fails if database is unavailable.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Upsert session record
                cur.execute("""
                    INSERT INTO user_sessions (
                        session_id, user_id, user_email, user_name, 
                        first_visit, last_activity
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) 
                    DO UPDATE SET 
                        last_activity = EXCLUDED.last_activity,
                        user_email = COALESCE(EXCLUDED.user_email, user_sessions.user_email),
                        user_name = COALESCE(EXCLUDED.user_name, user_sessions.user_name)
                """, (
                    session_id,
                    user_id,
                    user_email,
                    user_name,
                    datetime.utcnow(),
                    datetime.utcnow()
                ))
        return True
    except ValueError as ve:
        logger.debug(f"Session tracking unavailable: {ve}")
        return False
    except Exception as e:
        logger.warning(f"Failed to update session: {e}")
        return False


def generate_session_id() -> str:
    """Generate a unique session ID"""
    return str(uuid.uuid4())


def get_conversation_messages(conversation_id: str) -> List[Dict[str, Any]]:
    """
    Get all messages for a specific conversation using Databricks Genie API.
    
    Args:
        conversation_id: Conversation identifier
    
    Returns:
        List of messages with role and content
    """
    logger.info(f"📥 Fetching messages from Genie API for conversation_id: {conversation_id}")
    try:
        # Import here to avoid circular dependency
        from genie_room import GenieClient
        import os
        
        # Initialize Genie client
        space_id = os.environ.get("SPACE_ID")
        databricks_host = os.environ.get("DATABRICKS_HOST")
        
        if not space_id or not databricks_host:
            logger.error("SPACE_ID or DATABRICKS_HOST not configured")
            return []
        
        client = GenieClient(host=databricks_host, space_id=space_id)
        
        # Fetch messages from Genie API
        api_messages = client.list_conversation_messages(conversation_id)
        logger.info(f"📊 Genie API returned {len(api_messages)} messages for conversation {conversation_id}")
        
        # Format messages for UI
        formatted_messages = []
        
        for idx, msg in enumerate(api_messages):
            content = msg.get('content', '')
            attachments = msg.get('attachments', [])
            
            # Determine if this is a user message or assistant response
            # User messages typically don't have attachments
            if not attachments:
                # User message
                formatted_messages.append({
                    'role': 'user',
                    'content': content,
                    'message_id': msg.get('id'),
                    'timestamp': msg.get('created_timestamp')
                })
                logger.debug(f"✅ Added user message {idx}: {content[:50]}...")
            else:
                # Assistant response with attachments
                response_text = content
                sql_query = None
                
                # Extract SQL query from attachments if present
                for attachment in attachments:
                    if 'query' in attachment:
                        sql_query = attachment.get('query', {}).get('query', '')
                    elif 'text' in attachment and 'content' in attachment['text']:
                        response_text = attachment['text']['content']
                
                formatted_messages.append({
                    'role': 'assistant',
                    'content': response_text,
                    'sql_query': sql_query,
                    'message_id': msg.get('id'),
                    'timestamp': msg.get('created_timestamp')
                })
                logger.debug(f"✅ Added assistant message {idx}: {response_text[:50]}...")
        
        logger.info(f"✅ Returning {len(formatted_messages)} formatted messages for conversation {conversation_id}")
        return formatted_messages
        
    except Exception as e:
        logger.error(f"❌ Exception fetching messages from Genie API for {conversation_id}: {e}", exc_info=True)
        return []


def save_favorite(
    user_id: str,
    user_email: str,
    question: str,
    sql_query: str
) -> bool:
    """
    Save a favorite query to the database.
    
    Args:
        user_id: User identifier
        user_email: User's email address
        question: Synthesized plain text question
        sql_query: SQL query associated with the question
    
    Returns:
        bool: True if favorite was saved successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO user_favorites (
                        user_id, user_email, question, sql_query,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    user_email,
                    question,
                    sql_query,
                    datetime.utcnow(),
                    datetime.utcnow()
                ))
        logger.debug(f"✅ Saved favorite for user {user_id}")
        return True
    except ValueError as ve:
        logger.debug(f"Favorite save unavailable (no DB credentials): {ve}")
        return False
    except Exception as e:
        logger.error(f"Failed to save favorite: {e}")
        return False


def get_sql_usage_analytics(days: int = 30) -> Dict[str, Any]:
    """
    Analyze SQL queries to extract table and column usage statistics.
    
    Args:
        days: Number of days to look back (0 for all time)
    
    Returns:
        Dict with 'tables', 'columns', and 'table_columns' analytics
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build date filter
                date_filter = ""
                if days > 0:
                    date_filter = f"AND timestamp >= NOW() - INTERVAL '{days} days'"
                
                # Get all SQL queries
                cur.execute(f"""
                    SELECT 
                        metadata->>'sql_query' as sql_query
                    FROM user_events
                    WHERE event_type = 'sql_response'
                      AND metadata->>'sql_query' IS NOT NULL
                      {date_filter}
                """)
                
                results = cur.fetchall()
                
                # Parse all SQL queries and aggregate
                from collections import Counter
                table_counter = Counter()
                column_counter = Counter()
                table_column_counter = Counter()
                
                # Import the parsing function
                from stats_page import parse_sql_tables_and_columns
                
                for row in results:
                    sql_query = row[0]
                    if sql_query:
                        parsed = parse_sql_tables_and_columns(sql_query)
                        
                        # Count tables
                        for table in parsed['tables']:
                            table_counter[table] += 1
                            
                            # Count table-column pairs
                            for column in parsed['columns']:
                                table_column_counter[(table, column)] += 1
                        
                        # Count columns globally
                        for column in parsed['columns']:
                            column_counter[column] += 1
                
                # Format results
                tables = [{'table_name': table, 'count': count} 
                         for table, count in table_counter.items()]
                
                columns = [{'column_name': col, 'count': count} 
                          for col, count in column_counter.items()]
                
                table_columns = [{'table_name': table, 'column_name': col, 'count': count} 
                                for (table, col), count in table_column_counter.items()]
                
                return {
                    'tables': tables,
                    'columns': columns,
                    'table_columns': table_columns
                }
                
    except ValueError as ve:
        logger.debug(f"SQL analytics unavailable (no DB credentials): {ve}")
        return {'tables': [], 'columns': [], 'table_columns': []}
    except Exception as e:
        logger.warning(f"Failed to get SQL usage analytics: {e}")
        return {'tables': [], 'columns': [], 'table_columns': []}


def get_user_favorites(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all favorites for a user, sorted by newest first.
    
    Args:
        user_id: User identifier
    
    Returns:
        List of favorites with question, sql_query, and metadata
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        id,
                        question,
                        sql_query,
                        created_at
                    FROM user_favorites
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                """, (user_id,))
                
                results = cur.fetchall()
                return [{
                    'id': row[0],
                    'question': row[1],
                    'sql_query': row[2],
                    'created_at': row[3].isoformat() if row[3] else None
                } for row in results]
    except ValueError as ve:
        logger.debug(f"Favorites unavailable (no DB credentials): {ve}")
        return []
    except Exception as e:
        logger.warning(f"Failed to fetch user favorites: {e}")
        return []


def delete_user_favorite(favorite_id: int, user_id: str) -> bool:
    """
    Delete a specific favorite for a user.
    
    Args:
        favorite_id: ID of the favorite to delete
        user_id: User identifier (for security check)
    
    Returns:
        bool: True if deleted successfully, False otherwise
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM user_favorites
                    WHERE id = %s AND user_id = %s
                """, (favorite_id, user_id))
        logger.debug(f"✅ Deleted favorite {favorite_id} for user {user_id}")
        return True
    except ValueError as ve:
        logger.debug(f"Favorite delete unavailable (no DB credentials): {ve}")
        return False
    except Exception as e:
        logger.error(f"Failed to delete favorite: {e}")
        return False


def get_user_conversations(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get all conversations for a user, sorted by last activity.
    
    Args:
        user_id: User identifier from X-Forwarded-User header
        limit: Maximum number of conversations to return
    
    Returns:
        List of conversations with metadata
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    WITH conversation_summary AS (
                        SELECT 
                            conversation_id,
                            MIN(timestamp) FILTER (WHERE event_type = 'start_conversation') as started_at,
                            MAX(timestamp) as last_activity,
                            COUNT(*) FILTER (WHERE event_type = 'send_message') as message_count,
                            MAX(metadata->>'question') FILTER (WHERE event_type = 'start_conversation') as first_question
                        FROM user_events
                        WHERE user_id = %s 
                          AND conversation_id IS NOT NULL
                          AND event_type IN ('start_conversation', 'send_message')
                        GROUP BY conversation_id
                    )
                    SELECT 
                        conversation_id,
                        started_at,
                        last_activity,
                        message_count,
                        first_question
                    FROM conversation_summary
                    ORDER BY last_activity DESC
                    LIMIT %s
                """, (user_id, limit))
                
                results = cur.fetchall()
                return [{
                    'conversation_id': row[0],
                    'started_at': row[1].isoformat() if row[1] else None,
                    'last_activity': row[2].isoformat() if row[2] else None,
                    'message_count': row[3] or 0,
                    'first_question': row[4] or 'New conversation'
                } for row in results]
    except ValueError as ve:
        logger.debug(f"Conversation history unavailable: {ve}")
        return []
    except Exception as e:
        logger.warning(f"Failed to fetch user conversations: {e}")
        return []
