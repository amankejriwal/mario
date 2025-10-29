"""
Multi-page Mario Genie App with integrated stats dashboard.
Use this instead of app.py to include stats at /stats route.
"""

import dash
from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from flask import request
import logging

# Import main app components
from app import (
    app as main_app,
    get_user_from_request,
    DEFAULT_WELCOME_TITLE,
    DEFAULT_WELCOME_DESCRIPTION,
    DEFAULT_SUGGESTIONS
)

# Import stats components
from stats_page import create_stats_layout
from stats_app import (
    update_key_metrics, update_visitors_chart, update_activity_chart,
    update_conversation_trends, update_nps_display, update_feedback_trends,
    update_top_users, update_popular_questions, update_retention_chart,
    trigger_refresh
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the Flask server from main app
server = main_app.server

# Update app layout to include URL routing
main_app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# Import the original main app layout
def get_main_app_layout():
    """Get the main chat interface layout"""
    from app import app as original_app
    # Return everything except the routing wrapper
    return original_app.layout


@main_app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    """Route to different pages based on URL"""
    if pathname == '/stats':
        return html.Div([
            # Add navigation back to main app
            html.Div([
                html.A("← Back to Chat", href="/", className="stats-back-link")
            ], style={'padding': '20px', 'background': 'white'}),
            create_stats_layout()
        ])
    else:
        # Return main chat interface with stats link
        main_layout = get_main_app_layout()
        # Add stats navigation button
        return html.Div([
            html.Div([
                html.A("📊 View Analytics", href="/stats", className="stats-nav-link", 
                       style={
                           'position': 'fixed',
                           'top': '20px',
                           'right': '20px',
                           'padding': '10px 20px',
                           'background': '#667eea',
                           'color': 'white',
                           'border-radius': '8px',
                           'text-decoration': 'none',
                           'font-weight': '600',
                           'z-index': '1000',
                           'box-shadow': '0 2px 8px rgba(0,0,0,0.2)'
                       })
            ]),
            main_layout
        ])


# Register all stats callbacks with main app
# These are already defined in stats_app.py, just need to ensure they're registered
main_app.callback(
    Output('stats-refresh-trigger', 'data'),
    [Input('stats-refresh-btn', 'n_clicks'),
     Input('stats-interval', 'n_intervals')]
)(trigger_refresh)

main_app.callback(
    Output('key-metrics-cards', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)(update_key_metrics)

main_app.callback(
    Output('unique-visitors-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data'),
     Input('stats-time-filter', 'value')]
)(update_visitors_chart)

main_app.callback(
    Output('activity-by-hour-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)(update_activity_chart)

main_app.callback(
    Output('conversation-trends-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)(update_conversation_trends)

main_app.callback(
    Output('nps-score-display', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)(update_nps_display)

main_app.callback(
    Output('feedback-trends-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)(update_feedback_trends)

main_app.callback(
    Output('top-users-table', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)(update_top_users)

main_app.callback(
    Output('popular-questions-list', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)(update_popular_questions)

main_app.callback(
    Output('retention-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)(update_retention_chart)


if __name__ == '__main__':
    main_app.run_server(debug=True, host='0.0.0.0', port=8080)
