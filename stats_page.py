"""
Statistics dashboard for Mario Genie App.
Provides comprehensive analytics on user behavior, engagement, and feedback.
"""

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from typing import Dict, Any


def create_metric_card(title: str, value: Any, subtitle: str = "", icon: str = "📊"):
    """Create a metric card component"""
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Span(icon, className="metric-icon"),
                html.H3(str(value), className="metric-value"),
                html.H6(title, className="metric-title"),
                html.P(subtitle, className="metric-subtitle") if subtitle else None
            ])
        ])
    ], className="metric-card")


def create_stats_layout():
    """Create the main stats page layout"""
    return html.Div([
        # Header
        html.Div([
            html.Div([
                html.H1("📊 Mario Analytics Dashboard", className="stats-header-title"),
                html.P("Real-time insights into user behavior and engagement", className="stats-header-subtitle")
            ], className="stats-header-content"),
            html.Div([
                dcc.Dropdown(
                    id='stats-time-filter',
                    options=[
                        {'label': 'Last 7 Days', 'value': '7d'},
                        {'label': 'Last 30 Days', 'value': '30d'},
                        {'label': 'Last 90 Days', 'value': '90d'},
                        {'label': 'All Time', 'value': 'all'}
                    ],
                    value='30d',
                    className='stats-time-dropdown'
                ),
                html.Button("🔄 Refresh", id="stats-refresh-btn", className="stats-refresh-btn")
            ], className="stats-header-controls")
        ], className="stats-header"),
        
        # Key Metrics Overview
        html.Div([
            html.H2("📈 Key Metrics", className="section-title"),
            html.Div(id="key-metrics-cards", className="metrics-grid")
        ], className="stats-section"),
        
        # Engagement Charts
        html.Div([
            html.H2("👥 User Engagement", className="section-title"),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='unique-visitors-chart', config={'displayModeBar': False})
                ], width=6),
                dbc.Col([
                    dcc.Graph(id='activity-by-hour-chart', config={'displayModeBar': False})
                ], width=6)
            ]),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='conversation-trends-chart', config={'displayModeBar': False})
                ], width=12)
            ])
        ], className="stats-section"),
        
        # Feedback Analysis
        html.Div([
            html.H2("💬 Feedback Analysis", className="section-title"),
            dbc.Row([
                dbc.Col([
                    html.Div(id="nps-score-display", className="nps-container")
                ], width=4),
                dbc.Col([
                    dcc.Graph(id='feedback-trends-chart', config={'displayModeBar': False})
                ], width=8)
            ])
        ], className="stats-section"),
        
        # Top Users
        html.Div([
            html.H2("⭐ Top Active Users", className="section-title"),
            html.Div(id="top-users-table")
        ], className="stats-section"),
        
        # Popular Questions
        html.Div([
            html.H2("❓ Most Asked Questions", className="section-title"),
            html.Div(id="popular-questions-list")
        ], className="stats-section"),
        
        # User Retention
        html.Div([
            html.H2("🔄 User Retention", className="section-title"),
            dcc.Graph(id='retention-chart', config={'displayModeBar': False})
        ], className="stats-section"),
        
        # Auto-refresh interval
        dcc.Interval(
            id='stats-interval',
            interval=60*1000,  # Update every minute
            n_intervals=0
        ),
        
        # Store for refresh trigger
        dcc.Store(id='stats-refresh-trigger', data=0)
    ], className="stats-dashboard")


def create_nps_display(nps_data: Dict[str, Any]):
    """Create NPS score display"""
    nps = nps_data.get('nps', 0)
    
    # Determine NPS category and color
    if nps >= 50:
        category = "Excellent"
        color = "#10b981"
    elif nps >= 20:
        category = "Good"
        color = "#3b82f6"
    elif nps >= 0:
        category = "Needs Improvement"
        color = "#f59e0b"
    else:
        category = "Poor"
        color = "#ef4444"
    
    return html.Div([
        html.Div([
            html.H3("Net Promoter Score", className="nps-title"),
            html.Div([
                html.Span(f"{nps}", className="nps-value", style={'color': color}),
                html.Span(f" / 100", className="nps-max")
            ]),
            html.P(category, className="nps-category", style={'color': color}),
        ], className="nps-main"),
        html.Div([
            html.Div([
                html.Span("👍 ", className="nps-icon"),
                html.Span(f"{nps_data.get('promoters', 0)} ", className="nps-count"),
                html.Span(f"({nps_data.get('promoter_percentage', 0)}%)", className="nps-percent")
            ], className="nps-breakdown-item"),
            html.Div([
                html.Span("👎 ", className="nps-icon"),
                html.Span(f"{nps_data.get('detractors', 0)} ", className="nps-count"),
                html.Span(f"({nps_data.get('detractor_percentage', 0)}%)", className="nps-percent")
            ], className="nps-breakdown-item")
        ], className="nps-breakdown")
    ], className="nps-display")


def create_unique_visitors_chart(data: list):
    """Create unique visitors over time chart"""
    dates = [d['date'] for d in data]
    counts = [d['count'] for d in data]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=counts,
        mode='lines+markers',
        line=dict(color='#3b82f6', width=3),
        marker=dict(size=8),
        fill='tozeroy',
        fillcolor='rgba(59, 130, 246, 0.1)'
    ))
    
    fig.update_layout(
        title="Unique Visitors Over Time",
        xaxis_title="Date",
        yaxis_title="Unique Visitors",
        hovermode='x unified',
        template='plotly_white',
        height=300
    )
    
    return fig


def create_activity_by_hour_chart(data: list):
    """Create activity by hour of day chart"""
    hours = [d['hour'] for d in data]
    counts = [d['count'] for d in data]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=hours,
        y=counts,
        marker_color='#8b5cf6',
        text=counts,
        textposition='auto'
    ))
    
    fig.update_layout(
        title="Activity by Hour of Day",
        xaxis_title="Hour (24h format)",
        yaxis_title="Activity Count",
        template='plotly_white',
        height=300
    )
    
    return fig


def create_feedback_trends_chart(data: list):
    """Create feedback trends over time chart"""
    dates = [d['date'] for d in data]
    positive = [d['positive'] for d in data]
    negative = [d['negative'] for d in data]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=positive,
        name='Positive',
        mode='lines+markers',
        line=dict(color='#10b981', width=2),
        marker=dict(size=6)
    ))
    fig.add_trace(go.Scatter(
        x=dates,
        y=negative,
        name='Negative',
        mode='lines+markers',
        line=dict(color='#ef4444', width=2),
        marker=dict(size=6)
    ))
    
    fig.update_layout(
        title="Feedback Trends",
        xaxis_title="Date",
        yaxis_title="Feedback Count",
        hovermode='x unified',
        template='plotly_white',
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


def create_retention_chart(data: list):
    """Create user retention chart"""
    cohorts = [d['cohort_week'] for d in data]
    retention_rates = [d['retention_rate'] for d in data]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cohorts,
        y=retention_rates,
        marker_color='#06b6d4',
        text=[f"{r}%" for r in retention_rates],
        textposition='auto'
    ))
    
    fig.update_layout(
        title="User Retention by Cohort",
        xaxis_title="Cohort Week",
        yaxis_title="Retention Rate (%)",
        template='plotly_white',
        height=300
    )
    
    return fig


def create_top_users_table(users: list):
    """Create top users table"""
    if not users:
        return html.P("No user data available", className="no-data-message")
    
    table_header = [
        html.Thead(html.Tr([
            html.Th("Rank"),
            html.Th("User"),
            html.Th("Conversations"),
            html.Th("Messages"),
            html.Th("👍"),
            html.Th("👎"),
            html.Th("Total Activity")
        ]))
    ]
    
    rows = []
    for idx, user in enumerate(users, 1):
        rows.append(html.Tr([
            html.Td(f"#{idx}"),
            html.Td(user['user_email']),
            html.Td(user['conversations']),
            html.Td(user['messages']),
            html.Td(user['positive_feedback'], style={'color': '#10b981'}),
            html.Td(user['negative_feedback'], style={'color': '#ef4444'}),
            html.Td(html.Strong(user['total_activity']))
        ]))
    
    table_body = [html.Tbody(rows)]
    
    return dbc.Table(table_header + table_body, striped=True, bordered=True, hover=True, className="top-users-table")


def create_popular_questions_list(questions: list):
    """Create popular questions list"""
    if not questions:
        return html.P("No questions data available", className="no-data-message")
    
    items = []
    for idx, q in enumerate(questions[:10], 1):
        items.append(
            html.Div([
                html.Span(f"{idx}. ", className="question-rank"),
                html.Span(q['question'], className="question-text"),
                html.Span(f" ({q['count']}x)", className="question-count")
            ], className="question-item")
        )
    
    return html.Div(items, className="questions-list")


def create_conversation_trends_chart(engagement_data: Dict[str, Any]):
    """Create conversation trends chart"""
    metrics = ['Total Conversations', 'Total Messages', 'Total Feedback']
    values = [
        engagement_data.get('total_conversations', 0),
        engagement_data.get('total_messages', 0),
        engagement_data.get('total_feedback', 0)
    ]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=metrics,
        y=values,
        marker_color=['#3b82f6', '#8b5cf6', '#10b981'],
        text=values,
        textposition='auto'
    ))
    
    fig.update_layout(
        title="Overall Engagement Metrics",
        yaxis_title="Count",
        template='plotly_white',
        height=300
    )
    
    return fig
