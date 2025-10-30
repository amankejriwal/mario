-- Event Tracking Schema for Mario Genie App
-- This schema tracks all user interactions with the application

-- Table 1: user_events - Immutable event log for all user actions
CREATE TABLE IF NOT EXISTS user_events (
    event_id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,  -- 'page_visit', 'start_conversation', 'send_message', 'sql_response', 'feedback'
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    user_name VARCHAR(255),
    conversation_id VARCHAR(100),
    message_id VARCHAR(100),
    feedback_type VARCHAR(20),  -- 'positive' or 'negative' for feedback events
    session_id VARCHAR(100),  -- To track user sessions
    metadata JSONB,  -- Flexible field for additional data (questions, errors, etc.)
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_user_events_user_id ON user_events(user_id);
CREATE INDEX IF NOT EXISTS idx_user_events_event_type ON user_events(event_type);
CREATE INDEX IF NOT EXISTS idx_user_events_timestamp ON user_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_user_events_conversation_id ON user_events(conversation_id);
CREATE INDEX IF NOT EXISTS idx_user_events_session_id ON user_events(session_id);

-- Table 2: user_sessions - Aggregated view for quick user insights
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    user_name VARCHAR(255),
    first_visit TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    total_conversations INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    total_positive_feedback INTEGER DEFAULT 0,
    total_negative_feedback INTEGER DEFAULT 0
);

-- Indexes for user_sessions
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_last_activity ON user_sessions(last_activity);

-- View: Daily user activity summary
CREATE OR REPLACE VIEW daily_user_activity AS
SELECT 
    DATE(timestamp) as activity_date,
    user_id,
    user_email,
    COUNT(*) FILTER (WHERE event_type = 'page_visit') as page_visits,
    COUNT(*) FILTER (WHERE event_type = 'start_conversation') as conversations_started,
    COUNT(*) FILTER (WHERE event_type = 'send_message') as messages_sent,
    COUNT(*) FILTER (WHERE event_type = 'sql_response') as sql_queries_returned,
    COUNT(*) FILTER (WHERE event_type = 'feedback' AND feedback_type = 'positive') as positive_feedback,
    COUNT(*) FILTER (WHERE event_type = 'feedback' AND feedback_type = 'negative') as negative_feedback
FROM user_events
GROUP BY DATE(timestamp), user_id, user_email
ORDER BY activity_date DESC, conversations_started DESC;

-- View: Conversation success metrics
CREATE OR REPLACE VIEW conversation_metrics AS
SELECT 
    conversation_id,
    user_id,
    MIN(timestamp) as started_at,
    COUNT(*) FILTER (WHERE event_type = 'send_message') as message_count,
    COUNT(*) FILTER (WHERE event_type = 'feedback' AND feedback_type = 'positive') as positive_feedback,
    COUNT(*) FILTER (WHERE event_type = 'feedback' AND feedback_type = 'negative') as negative_feedback,
    CASE 
        WHEN COUNT(*) FILTER (WHERE event_type = 'feedback') > 0 THEN 'rated'
        ELSE 'unrated'
    END as feedback_status
FROM user_events
WHERE conversation_id IS NOT NULL
GROUP BY conversation_id, user_id
ORDER BY started_at DESC;

-- Table 3: user_favorites - User's saved favorite queries
CREATE TABLE IF NOT EXISTS user_favorites (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255),
    question TEXT NOT NULL,  -- Synthesized plain text question
    sql_query TEXT NOT NULL,  -- Original SQL query
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for user_favorites
CREATE INDEX IF NOT EXISTS idx_user_favorites_user_id ON user_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_user_favorites_created_at ON user_favorites(created_at);
