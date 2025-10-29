# Database Setup Guide for Event Logging

## 1. Create Database Tables

Run the SQL schema to create tables and views:

```bash
psql "host=instance-debc5f01-b417-48cc-9946-644617771b6f.database.azuredatabricks.net user=kejria01@heiway.net dbname=databricks_postgres port=5432 sslmode=require" < schema.sql
```

Or connect and run manually:
```bash
psql "host=instance-debc5f01-b417-48cc-9946-644617771b6f.database.azuredatabricks.net user=kejria01@heiway.net dbname=databricks_postgres port=5432 sslmode=require"
```

Then execute:
```sql
\i schema.sql
```

## 2. Set Up Databricks Secret for OAuth Token

**Important:** Databricks Lakehouse PostgreSQL uses **OAuth tokens** (not passwords) for authentication.

Store your OAuth token securely in Databricks:

```bash
# Create a secret scope (if not exists)
databricks secrets create-scope --scope db-secrets

# Store the OAuth token as db_password
databricks secrets put --scope db-secrets --key db_password
# When prompted, paste your OAuth token
```

The `event_logger.py` module will automatically:
1. Use the token from `DB_PASSWORD` environment variable, OR
2. Fall back to getting the token from Databricks SDK (`WorkspaceClient`)

`app.yaml` already references it:
```yaml
- name: DB_PASSWORD
  valueFrom: secret/db_password  # OAuth token for Lakehouse PostgreSQL
```

## 3. Verify Database Connection

Test the connection locally:

```python
from event_logger import get_db_connection

try:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            print("✅ Database connected:", cur.fetchone())
except Exception as e:
    print("❌ Connection failed:", e)
```

## 4. Tables Created

### `user_events`
- Primary event log for all user interactions
- Columns: event_id, event_type, user_id, user_email, user_name, conversation_id, message_id, feedback_type, session_id, metadata (JSONB), timestamp

### `user_sessions`
- Aggregated session data
- Columns: session_id, user_id, user_email, user_name, first_visit, last_activity, total_conversations, total_messages, total_positive_feedback, total_negative_feedback

### Views
- `daily_user_activity` - Daily aggregated metrics per user
- `conversation_metrics` - Per-conversation success metrics

## 5. Query Examples

**Most active users:**
```sql
SELECT user_email, COUNT(*) as total_events
FROM user_events
WHERE event_type = 'start_conversation'
GROUP BY user_email
ORDER BY total_events DESC
LIMIT 10;
```

**Feedback analysis:**
```sql
SELECT 
    user_email,
    COUNT(*) FILTER (WHERE feedback_type = 'positive') as thumbs_up,
    COUNT(*) FILTER (WHERE feedback_type = 'negative') as thumbs_down
FROM user_events
WHERE event_type = 'feedback'
GROUP BY user_email;
```

**Daily activity:**
```sql
SELECT * FROM daily_user_activity
WHERE activity_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY activity_date DESC;
```
