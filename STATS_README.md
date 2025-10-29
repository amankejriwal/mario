# Mario Analytics Dashboard

Comprehensive analytics dashboard for tracking user behavior, engagement, and feedback in the Mario Genie App.

## Features

### 📊 Key Metrics
- **Total Users** - Unique visitors count
- **Conversations Started** - Number of new conversations initiated
- **Total Messages** - All user messages sent
- **NPS Score** - Net Promoter Score based on feedback
- **Feedback Rate** - Percentage of conversations that received feedback
- **Avg Messages/Conversation** - Average engagement per conversation

### 📈 Visualizations

**User Engagement:**
- Unique visitors over time (daily trends)
- Activity by hour of day (peak usage times)
- Overall engagement metrics (conversations, messages, feedback)

**Feedback Analysis:**
- NPS score with promoter/detractor breakdown
- Feedback trends over time (positive vs negative)

**User Insights:**
- Top 10 most active users
- User retention by cohort
- Most asked questions (top 20)

## Running the Stats Dashboard

### Option 1: Standalone App

Run the stats dashboard as a separate application:

```bash
cd /path/to/genie_space
python stats_app.py
```

The dashboard will be available at: `http://localhost:8051`

### Option 2: Integrate with Main App

To add the stats page to your main Mario app:

1. Import stats components in `app.py`:
```python
from stats_app import app as stats_app
```

2. Add route handling for `/stats`

3. Navigate to `http://your-app-url/stats`

## Database Requirements

The dashboard queries the following tables:
- `user_events` - All user interaction events
- `user_sessions` - Aggregated session data

Make sure these tables are created and populated with data (see `schema.sql`).

## Auto-Refresh

The dashboard automatically refreshes every 60 seconds. You can also manually refresh using the 🔄 button.

## Metrics Explained

### Net Promoter Score (NPS)
- **Calculation**: `(Promoters - Detractors) / Total Feedback × 100`
- **Promoters**: Users who gave positive feedback (👍)
- **Detractors**: Users who gave negative feedback (👎)
- **Score Range**: -100 to +100
- **Interpretation**:
  - 50+: Excellent
  - 20-49: Good
  - 0-19: Needs Improvement
  - Below 0: Poor

### User Retention
Shows percentage of users from each cohort who returned after their first visit. Higher retention indicates better product stickiness.

### Activity by Hour
Identifies peak usage times, helping you understand when users are most active.

## Query Performance

All queries are optimized with indexes on:
- `user_id`
- `event_type`
- `timestamp`
- `conversation_id`
- `session_id`

For large datasets (>1M events), consider:
1. Adding date range filters
2. Materialized views for complex aggregations
3. Archiving old data

## Customization

### Adding New Metrics

1. Add query function to `stats_queries.py`
2. Add visualization function to `stats_page.py`
3. Add callback to `stats_app.py`
4. Update layout in `create_stats_layout()`

### Styling

Modify `assets/stats.css` to customize colors, fonts, and layout.

## Troubleshooting

**No data showing:**
- Ensure database connection is configured (check `DB_PASSWORD` env var)
- Verify tables are created: `psql ... < schema.sql`
- Check that event logging is working in main app

**Slow performance:**
- Check database indexes: `\d+ user_events` in psql
- Consider adding date range filters
- Review query execution plans

**Connection errors:**
- Verify OAuth token is valid
- Check service principal has database access
- Ensure Lakehouse PostgreSQL instance is accessible
