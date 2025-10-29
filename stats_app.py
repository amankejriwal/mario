"""
Main stats dashboard application for Mario Genie App.
Run this separately or integrate with main app.
"""

import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import logging
from stats_page import (
    create_stats_layout, create_metric_card, create_nps_display,
    create_unique_visitors_chart, create_activity_by_hour_chart,
    create_feedback_trends_chart, create_retention_chart,
    create_top_users_table, create_popular_questions_list,
    create_conversation_trends_chart
)
from stats_queries import (
    get_unique_visitors, get_nps_score, get_top_users,
    get_engagement_metrics, get_activity_by_hour,
    get_conversation_metrics, get_user_retention,
    get_feedback_over_time, get_popular_questions
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True
)

app.layout = create_stats_layout()


@app.callback(
    Output('stats-refresh-trigger', 'data'),
    [Input('stats-refresh-btn', 'n_clicks'),
     Input('stats-interval', 'n_intervals')]
)
def trigger_refresh(n_clicks, n_intervals):
    """Trigger refresh of all data"""
    return (n_clicks or 0) + n_intervals


@app.callback(
    Output('key-metrics-cards', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_key_metrics(trigger):
    """Update key metrics cards"""
    try:
        engagement = get_engagement_metrics()
        conversation = get_conversation_metrics()
        nps = get_nps_score()
        
        cards = [
            create_metric_card(
                "Total Users",
                engagement.get('total_users', 0),
                "Unique visitors",
                "👥"
            ),
            create_metric_card(
                "Conversations Started",
                engagement.get('total_conversations', 0),
                f"Avg {engagement.get('avg_messages_per_conversation', 0)} msgs/conv",
                "💬"
            ),
            create_metric_card(
                "Total Messages",
                engagement.get('total_messages', 0),
                "User interactions",
                "📨"
            ),
            create_metric_card(
                "NPS Score",
                nps.get('nps', 0),
                f"{nps.get('total', 0)} feedback responses",
                "⭐"
            ),
            create_metric_card(
                "Feedback Rate",
                f"{conversation.get('feedback_rate', 0)}%",
                f"{conversation.get('conversations_with_feedback', 0)} conversations rated",
                "📊"
            ),
            create_metric_card(
                "Avg Messages/Conv",
                conversation.get('avg_messages_per_conversation', 0),
                f"Median: {conversation.get('median_messages', 0)}",
                "📈"
            )
        ]
        
        return cards
    except Exception as e:
        logger.error(f"Error updating key metrics: {e}")
        return [html.P("Error loading metrics", className="error-message")]


@app.callback(
    Output('unique-visitors-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data'),
     Input('stats-time-filter', 'value')]
)
def update_visitors_chart(trigger, time_filter):
    """Update unique visitors chart"""
    try:
        data = get_unique_visitors('daily')
        return create_unique_visitors_chart(data['data'])
    except Exception as e:
        logger.error(f"Error updating visitors chart: {e}")
        return {}


@app.callback(
    Output('activity-by-hour-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_activity_chart(trigger):
    """Update activity by hour chart"""
    try:
        data = get_activity_by_hour()
        return create_activity_by_hour_chart(data)
    except Exception as e:
        logger.error(f"Error updating activity chart: {e}")
        return {}


@app.callback(
    Output('conversation-trends-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_conversation_trends(trigger):
    """Update conversation trends chart"""
    try:
        engagement = get_engagement_metrics()
        return create_conversation_trends_chart(engagement)
    except Exception as e:
        logger.error(f"Error updating conversation trends: {e}")
        return {}


@app.callback(
    Output('nps-score-display', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_nps_display(trigger):
    """Update NPS score display"""
    try:
        nps_data = get_nps_score()
        return create_nps_display(nps_data)
    except Exception as e:
        logger.error(f"Error updating NPS display: {e}")
        return html.P("Error loading NPS data")


@app.callback(
    Output('feedback-trends-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_feedback_trends(trigger):
    """Update feedback trends chart"""
    try:
        data = get_feedback_over_time()
        return create_feedback_trends_chart(data)
    except Exception as e:
        logger.error(f"Error updating feedback trends: {e}")
        return {}


@app.callback(
    Output('top-users-table', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_top_users(trigger):
    """Update top users table"""
    try:
        users = get_top_users(limit=10)
        return create_top_users_table(users)
    except Exception as e:
        logger.error(f"Error updating top users: {e}")
        return html.P("Error loading users data")


@app.callback(
    Output('popular-questions-list', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_popular_questions(trigger):
    """Update popular questions list"""
    try:
        questions = get_popular_questions()
        return create_popular_questions_list(questions)
    except Exception as e:
        logger.error(f"Error updating popular questions: {e}")
        return html.P("Error loading questions data")


@app.callback(
    Output('retention-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_retention_chart(trigger):
    """Update user retention chart"""
    try:
        data = get_user_retention()
        return create_retention_chart(data)
    except Exception as e:
        logger.error(f"Error updating retention chart: {e}")
        return {}


if __name__ == '__main__':
    app.run_server(debug=True, port=8051)
