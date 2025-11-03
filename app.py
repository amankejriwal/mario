import dash
import logging
from dash import html, dcc, Input, Output, State, ALL, MATCH, callback, callback_context, no_update, clientside_callback, dash_table
from flask import request, send_from_directory
import dash_bootstrap_components as dbc
import os
import json
from genie_room import genie_query
from token_minter import get_user_token_minter
import pandas as pd
import os
from dotenv import load_dotenv
import sqlparse
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from event_logger import log_page_visit, log_feedback, generate_session_id, update_session, get_user_conversations, get_conversation_messages, get_user_favorites, delete_user_favorite
from stats_page import create_stats_layout
import stats_queries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



load_dotenv()

# Create Dash app
app = dash.Dash(
    __name__,
    title="Mario",  # Browser tab title
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True  # Allow callbacks for components not in current layout
)

# Get Flask server for custom routes
server = app.server

# Route to serve Mario game files
@server.route('/mario/<path:path>')
def serve_mario(path):
    """Serve Mario game files"""
    mario_dir = os.path.join(os.path.dirname(__file__), 'mario')
    return send_from_directory(mario_dir, path)

# Get user info for event logging - will be populated from request headers
USER_INFO = None

def get_user_from_request():
    """Extract user info from Databricks forwarded headers"""
    try:
        user_id = request.headers.get("X-Forwarded-User")
        if user_id:
            return {
                'user_id': user_id,
                'user_email': user_id if '@' in user_id else None,
                'user_name': user_id
            }
    except Exception as e:
        logger.debug(f"Could not get user from headers: {e}")
    return None

# Add default welcome text that can be customized
DEFAULT_WELCOME_TITLE = "Mario - Product Data & Analytics Chatbot for Digital RtC"
DEFAULT_WELCOME_DESCRIPTION = "Deep dive into your product data, metrics, and insights. This data has been cleaned, reconciled, and is auto refreshed periodically."

# Add default suggestion questions
DEFAULT_SUGGESTIONS = [
    "Explain the dataset",
    "What tables are there and how are they connected? Give me a short summary.",
    "What is the average order value per OpCo, per month, in 2025",
    "How many active outlets did we have in Brazil in March 2025 ",
    "How many outlets churned in South Africa in March 2025"
]

def get_chat_layout():
    """Get the main chat interface layout"""
    return html.Div([
    # Top navigation bar
    html.Div([
        # Hamburger toggle button (top-left)
        html.Button([
            html.Div([
                html.Div(className="hamburger-line"),
                html.Div(className="hamburger-line"),
                html.Div(className="hamburger-line")
            ], className="hamburger-icon")
        ], id="sidebar-toggle", className="sidebar-toggle-button", title="Toggle Favorites"),
        
        # Favorites sidebar
        html.Div([
            html.Div([
                html.Div("My Favorites", className="sidebar-header-text"),
            ], className="sidebar-header"),
            html.Div([], className="favorites-list", id="favorites-list"),
            # Resize handle
            html.Div(className="sidebar-resize-handle", id="sidebar-resize-handle")
        ], id="sidebar", className="sidebar", style={'width': '0px'}),
        
        html.Div([
            html.Div("", id="logo-container", className="logo-container")
        ], className="nav-center"),
        html.Div([
            html.A("📊", href="/stats",
                   className="stats-nav-button",
                   title="Analytics Dashboard",
                   style={
                       'fontSize': '24px',
                       'textDecoration': 'none',
                       'padding': '8px 12px',
                       'borderRadius': '8px',
                       'transition': 'background 0.2s ease',
                       'display': 'inline-block'
                   })
     #       html.Div("Y", className="user-avatar"),
     #       html.A(
     #           html.Button(
     #               "Logout",
     #               id="logout-button",
     #               className="logout-button"
     #           ),
     #           href=f"https://{os.getenv('DATABRICKS_HOST')}/login.html",
     #           className="logout-link"
     #       )
        ], className="nav-right")
    ], className="top-nav"),
    
    # Main content area
    html.Div([
        html.Div([
            # Chat content
            html.Div([
                # Welcome container
                html.Div([
                    # Add settings button with tooltip
                    html.Div([
                        html.Div(id="welcome-title", className="welcome-message", children=[
                            html.Span("Mario", style={"color": "#E52521"}),
                            html.Span(" - Product Data & Analytics Chatbot for Digital RtC")
                        ]),
                        html.Button([
                            html.Img(src="assets/settings_icon.svg", className="settings-icon"),
                            html.Div("Customize welcome message", className="button-tooltip")
                        ],
                        id="edit-welcome-button",
                        className="edit-welcome-button",
                        title="Customize welcome message")
                    ], className="welcome-title-container"),
                    
                    html.Div(id="welcome-description", 
                            className="welcome-message-description",
                            children=DEFAULT_WELCOME_DESCRIPTION),
                    
                    # Add modal for editing welcome text
                    dbc.Modal([
                        dbc.ModalHeader(dbc.ModalTitle("Customize Welcome Message")),
                        dbc.ModalBody([
                            html.Div([
                                html.Label("Welcome Title", className="modal-label"),
                                dbc.Input(
                                    id="welcome-title-input",
                                    type="text",
                                    placeholder="Enter a title for your welcome message",
                                    className="modal-input"
                                ),
                                html.Small(
                                    "This title appears at the top of your welcome screen",
                                    className="text-muted d-block mt-1"
                                )
                            ], className="modal-input-group"),
                            html.Div([
                                html.Label("Welcome Description", className="modal-label"),
                                dbc.Textarea(
                                    id="welcome-description-input",
                                    placeholder="Enter a description that helps users understand the purpose of your application",
                                    className="modal-input",
                                    style={"height": "80px"}
                                ),
                                html.Small(
                                    "This description appears below the title and helps guide your users",
                                    className="text-muted d-block mt-1"
                                )
                            ], className="modal-input-group"),
                            html.Div([
                                html.Label("Suggestion Questions", className="modal-label"),
                                html.Small(
                                    "Customize the four suggestion questions that appear on the welcome screen",
                                    className="text-muted d-block mb-3"
                                ),
                                dbc.Input(
                                    id="suggestion-1-input",
                                    type="text",
                                    placeholder="First suggestion question",
                                    className="modal-input mb-2"
                                ),
                                dbc.Input(
                                    id="suggestion-2-input",
                                    type="text",
                                    placeholder="Second suggestion question",
                                    className="modal-input mb-2"
                                ),
                                dbc.Input(
                                    id="suggestion-3-input",
                                    type="text",
                                    placeholder="Third suggestion question",
                                    className="modal-input mb-2"
                                ),
                                dbc.Input(
                                    id="suggestion-4-input",
                                    type="text",
                                    placeholder="Fourth suggestion question",
                                    className="modal-input"
                                )
                            ], className="modal-input-group")
                        ]),
                        dbc.ModalFooter([
                            dbc.Button(
                                "Cancel",
                                id="close-modal",
                                className="modal-button",
                                color="light"
                            ),
                            dbc.Button(
                                "Save Changes",
                                id="save-welcome-text",
                                className="modal-button-primary",
                                color="primary"
                            )
                        ])
                    ], id="edit-welcome-modal", is_open=False, size="lg", backdrop="static"),

                    # Suggestion buttons with IDs
                    html.Div([
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Div("Explain the dataset", 
                                   className="suggestion-text", id="suggestion-1-text")
                        ], id="suggestion-1", className="suggestion-button"),
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Div("What tables are there and how are they connected? Give me a short summary.",
                                   className="suggestion-text", id="suggestion-2-text")
                        ], id="suggestion-2", className="suggestion-button"),
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Div("What is the average order value per OpCo, per month, in 2025?",
                                   className="suggestion-text", id="suggestion-3-text")
                        ], id="suggestion-3", className="suggestion-button"),
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Div("How many active outlets did we have in Brazil in March 2025?",
                                   className="suggestion-text", id="suggestion-4-text")
                        ], id="suggestion-4", className="suggestion-button"),
                        html.Button([
                            html.Div(className="suggestion-icon"),
                            html.Div("How many outlets churned in South Africa in March 2025?",
                                   className="suggestion-text", id="suggestion-5-text")
                        ], id="suggestion-5", className="suggestion-button")
                    ], className="suggestion-buttons")
                ], id="welcome-container", className="welcome-container visible"),
                
                # Chat messages
                html.Div([], id="chat-messages", className="chat-messages"),
                
                # Download component for CSV exports
                dcc.Download(id="download-dataframe-csv"),
            ], id="chat-content", className="chat-content"),
        ], id="chat-container", className="chat-container"),
        
        # Input area - moved outside chat-container to prevent scroll issues
        html.Div([
            html.Div([
                dcc.Input(
                    id="chat-input-fixed",
                    placeholder="Ask your question...",
                    className="chat-input",
                    type="text",
                    disabled=False
                ),
                html.Div([
                    html.Button(
                        id="send-button-fixed", 
                        className="input-button send-button",
                        disabled=False
                    )
                ], className="input-buttons-right"),
                html.Div("You can only submit one query at a time", 
                        id="query-tooltip", 
                        className="query-tooltip hidden")
            ], id="fixed-input-container", className="fixed-input-container"),
            html.Div("Mario v1.0", className="disclaimer-fixed")
        ], id="fixed-input-wrapper", className="fixed-input-wrapper"),
    ], id="main-content", className="main-content"),
    
    html.Div(id='dummy-output'),
    dcc.Store(id="chat-trigger", data={"trigger": False, "message": ""}),
    dcc.Store(id="chat-history-store", data=[]),
    dcc.Store(id="conversation-store", data={"conversation_id": None}),
    dcc.Store(id="query-running-store", data=False),
    dcc.Store(id="session-store", data={"current_session": None}),
    dcc.Store(id="page-visit-logged", data=False),  # Track if page visit was logged
    dcc.Store(id="export-clicks-tracker", data={}),  # Track processed export clicks
    dcc.Store(id="favorites-store", data=[]),  # Store user favorites
    dcc.Store(id="sidebar-state", data={"open": False, "width": 250})  # Sidebar state
    ])

# Define the app layout with URL routing
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

# Store chat history
chat_history = []

# Routing callback
@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/stats':
        return html.Div([
            html.Div([
                html.A("← Back to Chat", href="/", className="stats-back-link",
                       style={'padding': '20px', 'fontSize': '16px', 'fontWeight': '600', 
                              'color': '#667eea', 'textDecoration': 'none', 'display': 'block',
                              'background': 'white', 'borderBottom': '1px solid #e5e7eb'})
            ]),
            create_stats_layout()
        ])
    else:
        # Add stats link to chat layout
        chat_layout = get_chat_layout()
        return chat_layout

# Callback to log page visit event on app load
@app.callback(
    Output("page-visit-logged", "data"),
    Input("page-visit-logged", "data"),
    prevent_initial_call=False
)
def log_page_visit_event(logged):
    """Log page visit event on initial app load"""
    if not logged:
        user_info = get_user_from_request()
        if user_info:
            try:
                session_id = generate_session_id()
                log_page_visit(
                    user_id=user_info['user_id'],
                    user_email=user_info.get('user_email'),
                    user_name=user_info.get('user_name'),
                    session_id=session_id
                )
                # Update session record
                update_session(
                    session_id=session_id,
                    user_id=user_info['user_id'],
                    user_email=user_info.get('user_email'),
                    user_name=user_info.get('user_name')
                )
                logger.info(f"📍 Logged page visit for user {user_info['user_id']} (session: {session_id})")
                return True
            except Exception as e:
                logger.warning(f"Failed to log page visit: {e}")
    return logged if logged else False

# Callback to load favorites on page load
@app.callback(
    Output("favorites-store", "data"),
    Input("page-visit-logged", "data"),
    prevent_initial_call=False
)
def load_favorites_on_page_load(logged):
    """Load user's favorites from database on page load"""
    # Always attempt to load favorites, regardless of logged status
    user_info = get_user_from_request()
    
    # Fallback for local development without auth headers
    if not user_info:
        user_info = {
            'user_id': 'local_dev_user',
            'user_email': 'dev@localhost',
            'user_name': 'Local Developer'
        }
    
    try:
        favorites = get_user_favorites(user_info['user_id'])
        logger.info(f"⭐ Loaded {len(favorites)} favorites for user {user_info['user_id']}")
        return favorites
    except Exception as e:
        logger.warning(f"Failed to load favorites: {e}")
        import traceback
        logger.warning(traceback.format_exc())
    
    return []

# Callback to update favorites list in sidebar
@app.callback(
    Output("favorites-list", "children"),
    Input("favorites-store", "data"),
    prevent_initial_call=False
)
def update_favorites_list(favorites):
    """Update sidebar with user's favorites"""
    if not favorites:
        return html.Div("No favorites yet", style={'padding': '20px', 'textAlign': 'center', 'color': '#999', 'fontSize': '13px'})
    
    favorite_items = []
    for fav in favorites:
        favorite_items.append(
            html.Div([
                html.Button(
                    fav['question'],
                    id={"type": "favorite-item", "index": fav['id']},
                    className="favorite-item"
                ),
                # Delete button (shown initially)
                html.Button(
                    "Delete",
                    id={"type": "favorite-delete", "index": fav['id']},
                    className="favorite-delete-btn",
                    title="Delete favorite"
                ),
                # Confirm/Cancel buttons (shown after delete is clicked)
                html.Div([
                    html.Button(
                        "✓",
                        id={"type": "favorite-confirm-yes", "index": fav['id']},
                        className="favorite-confirm-btn favorite-confirm-yes",
                        title="Confirm delete"
                    ),
                    html.Button(
                        "✗",
                        id={"type": "favorite-confirm-no", "index": fav['id']},
                        className="favorite-confirm-btn favorite-confirm-no",
                        title="Cancel"
                    )
                ], id={"type": "favorite-confirm-container", "index": fav['id']},
                   className="favorite-confirm-container",
                   style={"display": "none"})  # Hidden initially
            ], className="favorite-item-container")
        )
    return favorite_items

# Callback to toggle sidebar open/close
@app.callback(
    Output("sidebar", "style"),
    Output("sidebar-state", "data"),
    Input("sidebar-toggle", "n_clicks"),
    State("sidebar-state", "data"),
    prevent_initial_call=True
)
def toggle_sidebar(n_clicks, sidebar_state):
    """Toggle sidebar open/closed"""
    if n_clicks:
        is_open = sidebar_state.get('open', False)
        new_width = 0 if is_open else sidebar_state.get('width', 250)
        
        return (
            {'width': f'{new_width}px'},
            {'open': not is_open, 'width': sidebar_state.get('width', 250)}
        )
    return no_update, no_update

def format_sql_query(sql_query):
    """Format SQL query with syntax highlighting"""
    import re
    
    # First format with sqlparse
    formatted_sql = sqlparse.format(
        sql_query,
        keyword_case='upper',
        identifier_case=None,
        reindent=True,
        indent_width=2,
        strip_comments=False,
        comma_first=False
    )
    
    # SQL keywords for highlighting
    keywords = [
        'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 
        'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'IS', 'NULL',
        'ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'OFFSET', 'AS', 'DISTINCT',
        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
        'UNION', 'INTERSECT', 'EXCEPT', 'WITH', 'INSERT', 'UPDATE', 'DELETE',
        'CREATE', 'ALTER', 'DROP', 'TABLE', 'VIEW', 'INDEX', 'INTO', 'VALUES',
        'SET', 'CAST', 'DATE', 'TIMESTAMP', 'INT', 'VARCHAR', 'DECIMAL'
    ]
    
    # Apply syntax highlighting
    highlighted = formatted_sql
    
    # Highlight keywords
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        highlighted = re.sub(
            pattern,
            f'<span class="sql-keyword">{keyword}</span>',
            highlighted,
            flags=re.IGNORECASE
        )
    
    # Highlight strings (single quotes)
    highlighted = re.sub(
        r"'([^']*)'",
        r"<span class='sql-string'>'\1'</span>",
        highlighted
    )
    
    # Highlight numbers
    highlighted = re.sub(
        r'\b(\d+\.?\d*)\b',
        r'<span class="sql-number">\1</span>',
        highlighted
    )
    
    # Highlight comments
    highlighted = re.sub(
        r'(--.*?$)',
        r'<span class="sql-comment">\1</span>',
        highlighted,
        flags=re.MULTILINE
    )
    
    return highlighted

def format_sql_with_pygments(sql_query):
    """Format SQL query using Pygments for proper syntax highlighting"""
    from pygments import highlight
    from pygments.lexers import SqlLexer
    from pygments.formatters import HtmlFormatter
    from bs4 import BeautifulSoup
    
    try:
        # First format with sqlparse
        formatted_sql = sqlparse.format(
            sql_query,
            keyword_case='upper',
            identifier_case=None,
            reindent=True,
            indent_width=2,
            strip_comments=False,
            comma_first=False
        )
        
        # Use Pygments to generate highlighted HTML
        lexer = SqlLexer()
        formatter = HtmlFormatter(nowrap=True, noclasses=False)
        highlighted_html = highlight(formatted_sql, lexer, formatter)
        
        # Parse HTML and convert to Dash components
        soup = BeautifulSoup(highlighted_html, 'html.parser')
        
        # Map Pygments classes to our CSS classes
        pygments_to_css = {
            'k': 'sql-keyword', 'kn': 'sql-keyword', 'kt': 'sql-keyword',
            's': 'sql-string', 's1': 'sql-string', 's2': 'sql-string',
            'm': 'sql-number', 'mi': 'sql-number', 'mf': 'sql-number',
            'c': 'sql-comment', 'c1': 'sql-comment', 'cm': 'sql-comment',
            'o': 'sql-operator',
            'n': 'sql-name',
            'nf': 'sql-function',
        }
        
        def process_element(element):
            """Recursively process HTML elements to Dash components"""
            if isinstance(element, str):
                return element
            
            if element.name == 'span':
                classes = element.get('class', [])
                css_class = None
                
                for pg_class in classes:
                    if pg_class in pygments_to_css:
                        css_class = pygments_to_css[pg_class]
                        break
                
                # Get text content
                text = element.get_text()
                
                if css_class:
                    return html.Span(text, className=css_class)
                else:
                    return text
            
            return element.get_text() if hasattr(element, 'get_text') else str(element)
        
        # Build components from soup
        result = []
        text_content = soup.get_text()
        
        # If parsing fails, just return formatted text
        if not highlighted_html or '<span' not in highlighted_html:
            return [formatted_sql]
        
        # Process each line
        for line in highlighted_html.split('\n'):
            if line.strip():
                line_soup = BeautifulSoup(line, 'html.parser')
                for child in line_soup.children:
                    comp = process_element(child)
                    if comp:
                        result.append(comp)
            result.append(html.Br())
        
        # Remove last Br
        if result and isinstance(result[-1], type(html.Br())):
            result.pop()
        
        logger.info(f"Pygments formatting successful, {len(result)} components generated")
        return result if result else [formatted_sql]
        
    except Exception as e:
        logger.error(f"Error formatting SQL with Pygments: {e}")
        # Fallback to plain formatted SQL
        fallback_sql = sqlparse.format(
            sql_query,
            keyword_case='upper',
            identifier_case=None,
            reindent=True,
            indent_width=2,
            strip_comments=False,
            comma_first=False
        )
        logger.info(f"Using fallback SQL formatting")
        return [fallback_sql]

def extract_table_names_from_sql(sql_query):
    """Extract table names from SQL query"""
    import re
    
    logger.info(f"Extracting table names from SQL query (first 300 chars): {sql_query[:300]}...")
    
    # Parse SQL to find table names after FROM and JOIN clauses
    # Pattern to handle backtick-qualified names: `catalog`.`schema`.`table`
    # Also handles: catalog.schema.table or schema.table or just table
    pattern = r'(?:FROM|JOIN)\s+(?:`([\w]+)`\.`([\w]+)`\.`([\w]+)`|`?([\w.]+)`?)(?:\s+(?:AS\s+)?\w+)?'
    matches = re.findall(pattern, sql_query, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    logger.info(f"Regex matches found: {matches}")
    
    # Process matches - they come as tuples with 4 groups
    table_names = []
    for match in matches:
        if match[0]:  # Backtick format: `catalog`.`schema`.`table`
            full_name = f"{match[0]}.{match[1]}.{match[2]}"
            table_names.append(full_name)
        elif match[3]:  # Regular format
            table_names.append(match[3])
    
    # Deduplicate
    table_names = list(set(table_names))
    
    logger.info(f"Cleaned table names: {table_names}")
    return table_names

def get_table_metadata(table_name):
    """Fetch table metadata from Databricks Unity Catalog"""
    try:
        from databricks.sdk import WorkspaceClient
        
        logger.info(f"Getting table metadata for: {table_name}")
        
        # Parse table name (could be catalog.schema.table or schema.table or just table)
        parts = table_name.split('.')
        logger.info(f"Table name parts: {parts}")
        
        if len(parts) == 3:
            catalog, schema, table = parts
        elif len(parts) == 2:
            catalog = 'hive_metastore'  # default catalog
            schema, table = parts
        else:
            logger.warning(f"Table name '{table_name}' doesn't have catalog.schema.table format")
            return None
        
        full_table_name = f"{catalog}.{schema}.{table}"
        logger.info(f"Fetching Unity Catalog metadata for: {full_table_name}")
        
        # Get table info using Unity Catalog API
        try:
            ws = WorkspaceClient()
            logger.info(f"WorkspaceClient initialized, calling ws.tables.get()")
            table_info = ws.tables.get(full_table_name)
            logger.info(f"Successfully fetched table info for {full_table_name}")
            
            metadata = {
                'name': table_info.name,
                'catalog': table_info.catalog_name,
                'schema': table_info.schema_name,
                'table_type': str(table_info.table_type) if table_info.table_type else 'TABLE',
                'comment': table_info.comment if hasattr(table_info, 'comment') and table_info.comment else None,
                'columns': []
            }
            
            # Get column information
            if hasattr(table_info, 'columns') and table_info.columns:
                logger.info(f"Found {len(table_info.columns)} columns")
                for col in table_info.columns:
                    col_type = col.type_name if hasattr(col, 'type_name') else (col.type_text if hasattr(col, 'type_text') else 'UNKNOWN')
                    metadata['columns'].append({
                        'name': col.name,
                        'type': col_type,
                        'comment': col.comment if hasattr(col, 'comment') and col.comment else None
                    })
            else:
                logger.info("No columns found in table_info")
            
            logger.info(f"Metadata extracted successfully: {metadata['name']} with {len(metadata['columns'])} columns")
            return metadata
            
        except Exception as e:
            logger.error(f"Unity Catalog API error for {full_table_name}: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
            
    except Exception as e:
        logger.error(f"Error in get_table_metadata: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def create_minimal_visualization(df):
    """Create minimal black and white visualizations based on data types"""
    import plotly.graph_objects as go
    import plotly.express as px
    
    if len(df) <= 1:
        return None
    
    logger.info(f"Creating visualization for dataframe with {len(df)} rows and {len(df.columns)} columns")
    
    # Analyze columns
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    logger.info(f"Numeric columns: {numeric_cols}, Categorical columns: {categorical_cols}")
    
    charts = []
    
    # Strategy: Create simple, flat visualizations
    # 1. If there's a categorical column and numeric columns, create bar charts
    # 2. If only numeric columns, create line charts
    # 3. Limit to first 2-3 most relevant charts
    
    if categorical_cols and numeric_cols:
        # Bar chart: categorical vs first numeric
        cat_col = categorical_cols[0]
        unique_cats = len(df[cat_col].unique())
        logger.info(f"Categorical column '{cat_col}' has {unique_cats} unique values")
        
        # Limit to top 10 categories to keep it clean
        if unique_cats <= 50:
            logger.info(f"Creating bar charts for categorical data (unique values: {unique_cats} <= 50)")
            for num_col in numeric_cols[:2]:  # Max 2 numeric columns
                fig = go.Figure()
                
                # Aggregate if needed
                grouped = df.groupby(cat_col)[num_col].sum().reset_index()
                grouped = grouped.sort_values(num_col, ascending=False).head(10)
                
                fig.add_trace(go.Bar(
                    x=grouped[cat_col],
                    y=grouped[num_col],
                    marker=dict(
                        color='black',
                        line=dict(color='black', width=1)
                    ),
                    name=num_col
                ))
                
                # Minimal styling
                fig.update_layout(
                    template='plotly_white',
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font=dict(family='Arial, sans-serif', size=11, color='black'),
                    margin=dict(l=50, r=20, t=30, b=50),
                    height=250,
                    showlegend=False,
                    xaxis=dict(
                        title=cat_col,
                        showgrid=False,
                        showline=True,
                        linecolor='black',
                        linewidth=1
                    ),
                    yaxis=dict(
                        title=num_col,
                        showgrid=True,
                        gridcolor='#e0e0e0',
                        gridwidth=0.5,
                        showline=True,
                        linecolor='black',
                        linewidth=1
                    )
                )
                
                logger.info(f"Bar chart created for {cat_col} vs {num_col}")
                charts.append(fig)
                logger.info(f"Chart appended, total charts now: {len(charts)}")
    
    elif len(numeric_cols) >= 2:
        # Line chart for numeric trends
        fig = go.Figure()
        
        # Use first column as x-axis if it looks like an index/time
        x_col = numeric_cols[0]
        
        for num_col in numeric_cols[1:3]:  # Max 2 lines
            fig.add_trace(go.Scatter(
                x=df[x_col],
                y=df[num_col],
                mode='lines+markers',
                name=num_col,
                line=dict(color='black', width=1.5),
                marker=dict(color='black', size=4)
            ))
        
        # Minimal styling
        fig.update_layout(
            template='plotly_white',
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family='Arial, sans-serif', size=11, color='black'),
            margin=dict(l=50, r=20, t=30, b=50),
            height=250,
            showlegend=True if len(numeric_cols) > 2 else False,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            xaxis=dict(
                title=x_col,
                showgrid=False,
                showline=True,
                linecolor='black',
                linewidth=1
            ),
            yaxis=dict(
                title='Value',
                showgrid=True,
                gridcolor='#e0e0e0',
                gridwidth=0.5,
                showline=True,
                linecolor='black',
                linewidth=1
            )
        )
        
        charts.append(fig)
    
    elif len(numeric_cols) == 1:
        # Simple horizontal bar for single numeric column
        num_col = numeric_cols[0]
        
        # Take top/bottom values
        sorted_df = df.nsmallest(10, num_col) if len(df) > 10 else df
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=sorted_df.index.astype(str) if categorical_cols == [] else sorted_df[categorical_cols[0]] if categorical_cols else sorted_df.index,
            x=sorted_df[num_col],
            orientation='h',
            marker=dict(
                color='black',
                line=dict(color='black', width=1)
            )
        ))
        
        fig.update_layout(
            template='plotly_white',
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family='Arial, sans-serif', size=11, color='black'),
            margin=dict(l=100, r=20, t=30, b=50),
            height=250,
            showlegend=False,
            xaxis=dict(
                title=num_col,
                showgrid=True,
                gridcolor='#e0e0e0',
                gridwidth=0.5,
                showline=True,
                linecolor='black',
                linewidth=1
            ),
            yaxis=dict(
                showgrid=False,
                showline=True,
                linecolor='black',
                linewidth=1
            )
        )
        
        logger.info(f"Line chart created")
        charts.append(fig)
        logger.info(f"Chart appended, total charts now: {len(charts)}")
    
    elif len(numeric_cols) == 1:
        # Simple horizontal bar for single numeric column
        num_col = numeric_cols[0]
        logger.info(f"Creating horizontal bar chart for single numeric column: {num_col}")
        
        # Take top/bottom values
        sorted_df = df.nsmallest(10, num_col) if len(df) > 10 else df
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=sorted_df.index.astype(str) if categorical_cols == [] else sorted_df[categorical_cols[0]] if categorical_cols else sorted_df.index,
            x=sorted_df[num_col],
            orientation='h',
            marker=dict(
                color='black',
                line=dict(color='black', width=1)
            )
        ))
        
        fig.update_layout(
            template='plotly_white',
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family='Arial, sans-serif', size=11, color='black'),
            margin=dict(l=100, r=20, t=30, b=50),
            height=250,
            showlegend=False,
            xaxis=dict(
                title=num_col,
                showgrid=True,
                gridcolor='#e0e0e0',
                gridwidth=0.5,
                showline=True,
                linecolor='black',
                linewidth=1
            ),
            yaxis=dict(
                showgrid=False,
                showline=True,
                linecolor='black',
                linewidth=1
            )
        )
        
        logger.info(f"Horizontal bar chart created")
        charts.append(fig)
        logger.info(f"Chart appended, total charts now: {len(charts)}")
    
    logger.info(f"Final: Generated {len(charts)} visualization(s)")
    logger.info(f"Returning: {charts if charts else None}")
    return charts if charts else None

def synthesize_question_from_sql(sql_query):
    """
    Synthesize a plain text question from SQL query using LLM.
    Args:
        sql_query: SQL query string
    Returns:
        str: Synthesized question that would generate this SQL
    """
    prompt = (
        "You are a helpful assistant that converts SQL queries into natural language questions. "
        "Given the SQL query below, generate a concise, natural language question that a user would ask "
        "to get this query as a result. Only return the question, nothing else.\n\n"
        f"SQL Query:\n{sql_query}\n\n"
        "Natural language question:"
    )
    
    try:
        client = WorkspaceClient()
        response = client.serving_endpoints.query(
            os.getenv("SERVING_ENDPOINT_NAME"),
            messages=[ChatMessage(content=prompt, role=ChatMessageRole.USER)],
        )
        synthesized_question = response.choices[0].message.content.strip()
        logger.info(f"Synthesized question: {synthesized_question}")
        return synthesized_question
    except Exception as e:
        logger.error(f"Error synthesizing question from SQL: {str(e)}")
        return f"Error synthesizing question: {str(e)}"


def call_llm_for_insights(df, prompt=None):
    """
    Call an LLM to generate insights from a DataFrame.
    Args:
        df: pandas DataFrame
        prompt: Optional custom prompt
    Returns:
        str: Insights generated by the LLM
    """
    if prompt is None:
        prompt = (
            "You are a professional data analyst. Given the following table data, "
            "provide deep, actionable analysis for 1. Key insights and trends 2. Notable patterns and" 
            " anomalies 3. Business implications."
            "Be thorough, professional, and concise.\n\n"
        )
    csv_data = df.to_csv(index=False)
    full_prompt = f"{prompt}Table data:\n{csv_data}"
    # Call OpenAI (replace with your own LLM provider as needed)
    try:
        client = WorkspaceClient()
        response = client.serving_endpoints.query(
            os.getenv("SERVING_ENDPOINT_NAME"),
            messages=[ChatMessage(content=full_prompt, role=ChatMessageRole.USER)],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating insights: {str(e)}"
    

# First callback: Handle inputs and show thinking indicator
@app.callback(
    [Output("chat-messages", "children", allow_duplicate=True),
     Output("chat-input-fixed", "value", allow_duplicate=True),
     Output("welcome-container", "className", allow_duplicate=True),
     Output("chat-trigger", "data", allow_duplicate=True),
     Output("query-running-store", "data", allow_duplicate=True),
     Output("chat-history-store", "data", allow_duplicate=True),
     Output("session-store", "data", allow_duplicate=True)],
    [Input("suggestion-1", "n_clicks"),
     Input("suggestion-2", "n_clicks"),
     Input("suggestion-3", "n_clicks"),
     Input("suggestion-4", "n_clicks"),
     Input("send-button-fixed", "n_clicks"),
     Input("chat-input-fixed", "n_submit")],
    [State("suggestion-1-text", "children"),
     State("suggestion-2-text", "children"),
     State("suggestion-3-text", "children"),
     State("suggestion-4-text", "children"),
     State("chat-input-fixed", "value"),
     State("chat-messages", "children"),
     State("welcome-container", "className"),
     State("chat-history-store", "data"),
     State("session-store", "data")],
    prevent_initial_call=True
)
def handle_all_inputs(s1_clicks, s2_clicks, s3_clicks, s4_clicks, send_clicks, submit_clicks,
                     s1_text, s2_text, s3_text, s4_text, input_value, current_messages,
                     welcome_class, chat_history, session_data):
    ctx = callback_context
    if not ctx.triggered:
        return [no_update] * 7

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Handle suggestion buttons
    suggestion_map = {
        "suggestion-1": s1_text,
        "suggestion-2": s2_text,
        "suggestion-3": s3_text,
        "suggestion-4": s4_text
    }
    
    # Get the user input based on what triggered the callback
    if trigger_id in suggestion_map:
        user_input = suggestion_map[trigger_id]
    else:
        user_input = input_value
    
    if not user_input:
        return [no_update] * 7
    
    # Create user message
    user_message = html.Div([
        html.Div(user_input, className="message-text")
    ], className="user-message message")
    
    # Add the user message to the chat
    updated_messages = current_messages + [user_message] if current_messages else [user_message]
    
    # Add thinking indicator
    thinking_indicator = html.Div([
        html.Div([
            html.Span(className="spinner"),
            html.Span("Thinking...")
        ], className="thinking-indicator")
    ], className="bot-message message")
    
    updated_messages.append(thinking_indicator)
    
    # Handle session management
    if session_data["current_session"] is None:
        session_data = {"current_session": len(chat_history) if chat_history else 0}
    
    current_session = session_data["current_session"]
    
    # Update chat history
    if chat_history is None:
        chat_history = []
    
    if current_session < len(chat_history):
        # Update existing conversation
        chat_history[current_session]["messages"] = updated_messages
        # Update title if this is first message in conversation
        if not chat_history[current_session].get("title") or chat_history[current_session].get("title") == "New conversation":
            chat_history[current_session]["title"] = user_input[:50] + '...' if len(user_input) > 50 else user_input
    else:
        # Create new conversation with standardized structure
        chat_history.insert(0, {
            "conversation_id": None,  # Will be set after API response
            "title": user_input[:50] + '...' if len(user_input) > 50 else user_input,
            "messages": updated_messages,
            "message_count": 1
        })
    
    # Chat list will be automatically updated by update_sidebar_from_history callback
    # when chat_history changes
    
    return (updated_messages, "", "welcome-container hidden",
            {"trigger": True, "message": user_input}, True,
            chat_history, session_data)

# Second callback: Make API call and show response
@app.callback(
    [Output("chat-messages", "children", allow_duplicate=True),
     Output("chat-history-store", "data", allow_duplicate=True),
     Output("conversation-store", "data"),
     Output("chat-trigger", "data", allow_duplicate=True),
     Output("query-running-store", "data", allow_duplicate=True)],
    [Input("chat-trigger", "data")],
    [State("chat-messages", "children"),
     State("chat-history-store", "data"),
     State("conversation-store", "data")],
    prevent_initial_call=True
)
def get_model_response(trigger_data, current_messages, chat_history, conversation_store):
    if not trigger_data or not trigger_data.get("trigger"):
        return [dash.no_update] * 5
    
    user_input = trigger_data.get("message", "")
    if not user_input:
        return [dash.no_update] * 5
    
    # Check for Mario easter egg
    normalized = ''.join(c for c in user_input.lower() if c.isalnum() or c.isspace())
    normalized = ' '.join(normalized.split())  # Remove extra spaces
    
    if normalized == "i love data":
        # Remove thinking indicator if present
        if current_messages and len(current_messages) > 0:
            last_message = current_messages[-1]
            if isinstance(last_message, dict) and 'props' in last_message:
                if 'className' in last_message['props'] and 'thinking-indicator' in str(last_message['props'].get('className', '')):
                    current_messages = current_messages[:-1]
        
        # Create Mario game message
        mario_message = html.Div([
            html.Div([
                html.Img(src="assets/mario_avatar.svg", className="model-avatar"),
                html.Span("Mario", className="model-name")
            ], className="bot-info"),
            html.Div([
                html.Div([
                    html.Div("🎮 Easter Egg Unlocked!", 
                            style={"marginBottom": "10px", "fontWeight": "600"}),
                    html.Iframe(
                        id="mario-game-iframe",
                        src="/mario/index.html",
                        className="mario-game-iframe",
                        style={
                            "width": "512px",
                            "height": "500px",
                            "border": "2px solid #667eea",
                            "borderRadius": "8px",
                            "background": "black"
                        }
                    )
                ], className="mario-game-container")
            ], className="message-text")
        ], className="bot-message message", id={"type": "mario-game", "index": 0})
        
        updated_messages = current_messages + [mario_message]
        return (updated_messages, chat_history, conversation_store, 
                {"trigger": False, "message": ""}, False)
    
    try:
        # Get current conversation ID
        conversation_id = None
        if conversation_store and "conversation_id" in conversation_store:
            conversation_id = conversation_store["conversation_id"]
        
        # Get user-specific token minter
        token_minter = get_user_token_minter()
        
        # Get user info from request headers for event logging
        user_info = get_user_from_request()
        
        # Fallback for local development without auth headers
        if not user_info:
            user_info = {
                'user_id': 'local_dev_user',
                'user_email': 'dev@localhost',
                'user_name': 'Local Developer'
            }
        
        # Make the API call with user-specific authentication and event logging
        response, query_text, new_conversation_id = genie_query(user_input, conversation_id, token_minter, user_info)
        
        # Update conversation ID if this was a new conversation
        if new_conversation_id and new_conversation_id != conversation_id:
            conversation_store = {"conversation_id": new_conversation_id}
        
        # Create a unique ID for this message using timestamp and a random number
        import time
        import random
        message_id = f"{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        table_id = f"table-{message_id}"
        
        # Initialize buttons to None (will be set conditionally)
        show_code_button = None
        star_button = None
        favorites_section = None
        success_toast = None
        insight_button = None
        export_button = None
        query_section = None
        
        if isinstance(response, str):
            content = dcc.Markdown(response, className="message-text")
        else:
            # Data table response
            df = pd.DataFrame(response)
            
            # Convert string columns that look like numbers to actual numeric types
            for col in df.columns:
                if df[col].dtype == 'object':  # String column
                    try:
                        # Try to convert to numeric
                        df[col] = pd.to_numeric(df[col], errors='ignore')
                    except:
                        pass
            
            # Generate visualizations if data has more than 1 row
            charts = None
            if len(df) > 1:
                try:
                    logger.info(f"Attempting to generate visualization for dataframe with {len(df)} rows")
                    charts = create_minimal_visualization(df)
                    if charts:
                        logger.info(f"Successfully generated {len(charts)} chart(s)")
                    else:
                        logger.info("No charts generated (returned None)")
                except Exception as e:
                    logger.error(f"Error generating visualization: {type(e).__name__}: {str(e)}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    charts = None
            else:
                logger.info(f"Not generating visualization - only {len(df)} row(s)")
            
            # Create columns with EU number formatting for numeric columns
            from dash_table.Format import Format, Group, Scheme
            columns = []
            for col in df.columns:
                if pd.api.types.is_numeric_dtype(df[col]):
                    # Check if column has decimals
                    has_decimals = df[col].dtype in ['float64', 'float32']
                    if not has_decimals and len(df[col]) > 0:
                        # Check if any values have decimals for integer columns
                        try:
                            has_decimals = (df[col] % 1 != 0).any()
                        except:
                            pass
                    
                    if has_decimals:
                        # Format with 2 decimals, EU style (dot for thousands, comma for decimal)
                        columns.append({
                            "name": col,
                            "id": col,
                            "type": "numeric",
                            "format": Format(
                                scheme=Scheme.fixed,
                                precision=2,
                                group=Group.yes,
                                group_delimiter='.',
                                decimal_delimiter=','
                            )
                        })
                    else:
                        # Format integers with thousand separators, no decimals
                        columns.append({
                            "name": col,
                            "id": col,
                            "type": "numeric",
                            "format": Format(
                                scheme=Scheme.fixed,
                                precision=0,
                                group=Group.yes,
                                group_delimiter='.',
                                decimal_delimiter=','
                            )
                        })
                else:
                    # Non-numeric columns
                    columns.append({"name": col, "id": col})
            
            # Create the table with adjusted styles
            data_table = dash_table.DataTable(
                id=f"table-{len(chat_history)}",
                data=df.to_dict('records'),
                columns=columns,
                
                # Export configuration
                export_format="csv",
                export_headers="display",
                
                # Disable editing to allow text selection
                editable=False,
                
                # Other table properties
                page_size=10,
                style_table={
                    'display': 'block',
                    'overflowX': 'auto',
                    'width': '95%',
                    'marginRight': '20px',
                    'border': '1px solid #eaecef',
                    'borderRadius': '4px'
                },
                style_cell={
                    'textAlign': 'left',
                    'fontSize': '12px',
                    'padding': '4px 10px',
                    'fontFamily': '-apple-system, BlinkMacSystemFont,Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif',
                    'backgroundColor': 'transparent',
                    'maxWidth': 'fit-content',
                    'minWidth': '100px',
                    'cursor': 'text'
                },
                style_header={
                    'backgroundColor': '#f8f9fa',
                    'fontWeight': '600',
                    'borderBottom': '1px solid #eaecef',
                    'cursor': 'text'
                },
                style_data={
                    'whiteSpace': 'normal',
                    'height': 'auto'
                },
                fill_width=False,
                page_current=0,
                page_action='native'
            )

            # Format SQL query if available
            query_section = None
            if query_text is not None:
                # Format SQL with Pygments for proper syntax highlighting
                formatted_sql_components = format_sql_with_pygments(query_text)
                query_index = f"{len(chat_history)}-{len(current_messages)}"
                
                # Show code button (pill-shaped)
                show_code_button = html.Button([
                    html.Span("Show code", id={"type": "toggle-text", "index": query_index})
                ], 
                id={"type": "toggle-query", "index": query_index}, 
                className="toggle-query-button",
                style={
                    "borderRadius": "50px",
                    "padding": "4px 10px",
                    "background-color": "white",
                    "border": "2px solid gold",
                    "cursor": "pointer",
                    "fontSize": "13px",
                    "transition": "all 0.2s ease",
                    "textDecoration": "none" 
                },
                n_clicks=0)
                
                # Star button for favorites (gold/yellow) with SQL data stored inline
                star_button = html.Div([
                    html.Button(
                        "☆",
                        id={"type": "star-button", "index": query_index},
                        className="star-button",
                        title="Add to favorites",
                        style={
                            "padding": "4px 10px",
                            "backgroundColor": "white",
                            "color": "#FFD700",
                            "border": "2px solid #FFD700",
                            "borderRadius": "6px",
                            "fontSize": "16px",
                            "cursor": "pointer",
                            "transition": "all 0.2s ease",
                            "fontWeight": "bold"
                        },
                        n_clicks=0
                    ),
                    # Store SQL query with the button
                    dcc.Store(
                        id={"type": "star-sql-store", "index": query_index},
                        data=query_text
                    )
                ], style={"display": "inline-block"})
                
                # Favorites section (hidden by default, shown after star click)
                favorites_section = html.Div(
                    [
                        html.Div([
                            dcc.Textarea(
                                id={"type": "favorite-textarea", "index": query_index},
                                placeholder="Synthesizing question...",
                                className="favorite-textarea",
                                style={
                                    "width": "100%",
                                    "minHeight": "60px",
                                    "maxHeight": "150px",
                                    "padding": "10px",
                                    "borderRadius": "8px",
                                    "border": "1px solid #FFD700",
                                    "fontSize": "13px",
                                    "fontFamily": "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
                                    "resize": "vertical",
                                    "marginBottom": "8px"
                                },
                                value=""
                            ),
                            html.Button(
                                "Save to Favorites",
                                id={"type": "save-favorite-button", "index": query_index},
                                className="save-favorite-button",
                                style={
                                    "padding": "6px 16px",
                                    "backgroundColor": "#FFD700",
                                    "color": "#000",
                                    "border": "none",
                                    "borderRadius": "6px",
                                    "fontSize": "13px",
                                    "cursor": "pointer",
                                    "fontWeight": "600"
                                }
                            )
                        ], style={"padding": "12px", "backgroundColor": "#FFFEF0", "borderRadius": "8px", "border": "1px solid #FFD700"})
                    ],
                    id={"type": "favorites-section", "index": query_index},
                    className="favorites-section",
                    style={"display": "none", "marginTop": "12px"}
                )
                
                # Success toast message with close button (hidden by default)
                success_toast = html.Div([
                    html.Span("✓ Added to your favorites. Access it from the right side navigation.", 
                             style={"flex": "1"}),
                    html.Button(
                        "×",
                        id={"type": "close-toast", "index": query_index},
                        style={
                            "background": "none",
                            "border": "none",
                            "color": "#000",
                            "fontSize": "20px",
                            "cursor": "pointer",
                            "padding": "0 0 0 12px",
                            "fontWeight": "bold"
                        },
                        title="Close"
                    )
                ],
                    id={"type": "success-toast", "index": query_index},
                    className="success-toast",
                    style={
                        "display": "none",
                        "backgroundColor": "#FFF4CC",
                        "color": "#000",
                        "padding": "12px 16px",
                        "borderRadius": "8px",
                        "marginTop": "12px",
                        "fontSize": "13px",
                        "fontWeight": "500",
                        "border": "1px solid #FFD700",
                        "alignItems": "center",
                        "justifyContent": "space-between"
                    }
                )
                
                # Extract table names and fetch metadata
                table_names = extract_table_names_from_sql(query_text)
                logger.info(f"Extracted table names from SQL: {table_names}")
                tables_metadata = []
                for table_name in table_names:
                    logger.info(f"Fetching metadata for table: {table_name}")
                    metadata = get_table_metadata(table_name)
                    if metadata:
                        tables_metadata.append(metadata)
                        logger.info(f"Successfully fetched metadata for {table_name}")
                    else:
                        logger.warning(f"No metadata found for table: {table_name}")
                
                logger.info(f"Total tables with metadata: {len(tables_metadata)}")
                
                # Build table metadata section
                metadata_section = None
                if tables_metadata:
                    metadata_items = []
                    for meta in tables_metadata:
                        # Table header
                        metadata_items.append(html.Div([
                            html.Div(f"{meta['catalog']}.{meta['schema']}.{meta['name']}", 
                                    style={'fontWeight': '600', 'fontSize': '14px', 'marginBottom': '4px'}),
                            html.Div(f"Type: {meta['table_type']}", 
                                    style={'fontSize': '12px', 'opacity': '0.8', 'marginBottom': '4px'}),
                            html.Div(meta['comment'] if meta['comment'] else 'No description available', 
                                    style={'fontSize': '12px', 'marginBottom': '8px'}),
                        ], style={'marginBottom': '12px'}))
                        
                        # Columns (show first 5)
                        if meta['columns']:
                            col_items = []
                            for col in meta['columns'][:5]:
                                col_text = f"• {col['name']} ({col['type']})"
                                if col['comment']:
                                    col_text += f" - {col['comment']}"
                                col_items.append(html.Div(col_text, style={'fontSize': '11px', 'marginLeft': '8px', 'marginBottom': '2px'}))
                            
                            if len(meta['columns']) > 5:
                                col_items.append(html.Div(f"... and {len(meta['columns']) - 5} more columns", 
                                                         style={'fontSize': '11px', 'marginLeft': '8px', 'fontStyle': 'italic', 'opacity': '0.7'}))
                            
                            metadata_items.append(html.Div(col_items, style={'marginBottom': '16px'}))
                    
                    metadata_section = html.Div([
                        html.Div("📊 Tables Used", style={'fontWeight': '600', 'fontSize': '13px', 'marginBottom': '12px', 'borderTop': '1px solid #444', 'paddingTop': '12px'}),
                        html.Div(metadata_items)
                    ], style={'marginTop': '16px'})
                    logger.info(f"Created metadata section with {len(metadata_items)} items")
                else:
                    logger.info("No metadata section created - tables_metadata is empty")
                
                # SQL code container (hidden by default)
                code_content = [html.Pre(
                    formatted_sql_components,
                    className="sql-pre",
                    style={'margin': '0'}
                )]
                
                if metadata_section:
                    code_content.append(metadata_section)
                    logger.info("Metadata section appended to code_content")
                else:
                    logger.info("No metadata section to append")
                
                query_code_container = html.Div(
                    code_content,
                    id={"type": "query-code", "index": query_index}, 
                    className="query-code-container hidden"
                )
                
                query_section = html.Div([
                    query_code_container
                ], id={"type": "query-section", "index": query_index}, className="query-section")
            
            # Generate Insights button (simple button without spinner)
            insight_button = html.Button(
                "Generate Insights",
                id={"type": "insight-button", "index": table_id},
                className="insight-button",
                style={"border": "none", "background": "#f0f0f0", "padding": "8px 16px", "borderRadius": "4px", "cursor": "pointer"}
            )
            # Custom loading indicator with spinner and rotating text
            insight_output = html.Div(
                id={"type": "insight-output", "index": table_id},
                children=[
                    # Loading indicator (hidden by default, shown when generating)
                    html.Div([
                        html.Span(className="spinner"),
                        html.Div([
                            html.Span("Studying data...", className="rotating-text"),
                            html.Span("Talking to LLM...", className="rotating-text"),
                            html.Span("Summarizing key points...", className="rotating-text")
                        ], className="rotating-text-container")
                    ], className="insight-loading-indicator", style={"display": "none"})
                ],
                style={"marginTop": "12px"}
            )
            
            # Store table_id in dataframes for later retrieval
            if chat_history and len(chat_history) > 0:
                chat_history[0].setdefault('dataframes', {})[table_id] = df.to_json(orient='split')
            
            # Create Export button for tables
            export_button = html.Button(
                "Export",
                id={"type": "export-button", "index": table_id},
                className="export-button",
                style={
                    "padding": "4px 10px",
                    "backgroundColor": "#ECFADC",
                    "color": "#4A5D23",
                    "border": "1px solid #C5E898",
                    "borderRadius": "6px",
                    "fontSize": "13px",
                    "transition": "all 0.2s ease"
                }
            )

            # Create content with table and optional visualizations
            content_items = [
                html.Div([data_table], style={
                    'marginBottom': '20px',
                    'paddingLeft': '0px',
                    'paddingRight': '5px'
                })
            ]
            
            # Add visualizations if they were generated
            if charts:
                logger.info(f"Adding {len(charts)} chart(s) to content")
                for idx, chart in enumerate(charts):
                    chart_id = f"chart-{message_id}-{idx}"
                    content_items.append(
                        html.Div([
                            html.Div([
                                html.Button(
                                    "📷",
                                    id={"type": "download-chart", "index": chart_id},
                                    className="download-chart-button",
                                    title="Download as PNG",
                                    style={
                                        "position": "absolute",
                                        "top": "8px",
                                        "right": "8px",
                                        "padding": "6px 10px",
                                        "backgroundColor": "white",
                                        "border": "1px solid #ddd",
                                        "borderRadius": "6px",
                                        "fontSize": "16px",
                                        "cursor": "pointer",
                                        "zIndex": "1000",
                                        "boxShadow": "0 2px 4px rgba(0,0,0,0.1)",
                                        "transition": "all 0.2s ease"
                                    }
                                )
                            ], style={"position": "relative"}),
                            dcc.Graph(
                                id=chart_id,
                                figure=chart,
                                config={
                                    'displayModeBar': False,
                                    'staticPlot': False,
                                    'toImageButtonOptions': {
                                        'format': 'png',
                                        'filename': f'mario_chart_{int(time.time())}',
                                        'height': 500,
                                        'width': 700,
                                        'scale': 2
                                    }
                                },
                                style={'marginBottom': '16px'}
                            )
                        ], style={'marginTop': '16px', 'position': 'relative'})
                    )
            
            content = html.Div(content_items)
        
        # Create action buttons row (Export, Show code, Generate Insights, Thumbs up/down)
        action_buttons = html.Div([
            # Export button (only for tables) - FIRST BUTTON
            export_button,
            # Show code button (only if query exists)
            show_code_button,
            # Thumbs up/down buttons
            html.Button(
                id={"type": "thumbs-up-button", "index": message_id},
                className="thumbs-up-button",
                title="This response was helpful"
            ),
            html.Button(
                id={"type": "thumbs-down-button", "index": message_id},
                className="thumbs-down-button",
                title="This response was not helpful"
            ),
            # Generate Insights button (without spinner inline)
            insight_button,
            # Star button for favorites (only if query exists)
            star_button
        ], className="message-actions", style={
            "display": "flex",
            "gap": "8px",
            "alignItems": "center",
            "marginTop": "12px"
        })
        
        # Comment textarea for negative feedback (hidden by default)
        comment_section = html.Div([
            html.Div([
                dcc.Textarea(
                    id={"type": "comment-textarea", "index": message_id},
                    placeholder="Tell us what went wrong...",
                    className="comment-textarea",
                    style={
                        "width": "100%",
                        "minHeight": "40px",
                        "maxHeight": "200px",
                        "padding": "10px 50px 10px 10px",
                        "borderRadius": "8px",
                        "border": "1px solid #d1d9e1",
                        "fontSize": "13px",
                        "fontFamily": "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
                        "resize": "vertical"
                    }
                ),
                html.Button(
                    "Send",
                    id={"type": "send-comment-button", "index": message_id},
                    className="send-comment-button",
                    style={
                        "position": "absolute",
                        "right": "10px",
                        "top": "10px",
                        "padding": "6px 12px",
                        "backgroundColor": "#667eea",
                        "color": "white",
                        "border": "none",
                        "borderRadius": "4px",
                        "cursor": "pointer",
                        "fontSize": "12px",
                        "fontWeight": "600"
                    },
                    n_clicks=0
                )
            ], style={"position": "relative", "marginTop": "8px"}),
            # Success message (hidden by default)
            html.Div([
                "Thank you for the constructive input. We will review and respond soon!",
                dcc.Interval(
                    id={"type": "success-message-timer", "index": message_id},
                    interval=2000,  # 2 seconds
                    n_intervals=0,
                    max_intervals=1,  # Only trigger once
                    disabled=True  # Start disabled
                )
            ],
                id={"type": "comment-success-message", "index": message_id},
                style={
                    "display": "none",
                    "marginTop": "8px",
                    "padding": "8px 12px",
                    "backgroundColor": "#d4edda",
                    "color": "#155724",
                    "border": "1px solid #c3e6cb",
                    "borderRadius": "4px",
                    "fontSize": "13px"
                }
            )
        ], id={"type": "comment-section", "index": message_id}, style={"display": "none"})
        
        # Create sections that appear below buttons (code, insights, favorites)
        below_buttons_section = html.Div([
            # SQL code section (appears when Show code is clicked)
            query_section if query_section else None,
            # Insights output with spinner (appears when Generate Insights is clicked)
            insight_output if insight_button else None,
            # Favorites section (appears when Star button is clicked)
            favorites_section if favorites_section else None,
            # Success toast with close button (appears after saving favorite)
            success_toast if success_toast else None
        ])
        
        # Build list of bot response children
        bot_response_children = [
            # Hidden div to store message index
            dcc.Store(
                id={"type": "message-index", "index": message_id},
                data={"index": message_id}
            ),
            
            # Toast for feedback confirmation
            dbc.Toast(
                id={"type": "feedback-toast", "index": message_id},
                header="Feedback",
                is_open=False,
                dismissable=True,
                duration=4000,
                style={"position": "fixed", "top": 66, "right": 10, "width": 350},
            ),
            
            # Message content
            html.Div([
                html.Img(src="assets/mario_avatar.svg", className="model-avatar"),
                html.Span("Mario", className="model-name")
            ], className="model-info"),
            
            # Message content with action buttons and sections below
            html.Div([
                content,
                action_buttons,
                comment_section,
                below_buttons_section
            ], className="message-content")
        ]
        
        # Create bot response div
        bot_response = html.Div(bot_response_children, className="bot-message message")
        
        # Update chat history with both user message and bot response
        updated_messages = current_messages[:-1] + [bot_response]
        if chat_history and len(chat_history) > 0:
            chat_history[0]["messages"] = updated_messages
            
        return (
            updated_messages,  # chat-messages.children
            chat_history,      # chat-history-store.data
            conversation_store, # conversation-store.data
            {"trigger": False, "message": ""},  # chat-trigger.data
            False              # query-running-store.data
        )
        
    except Exception as e:
        error_msg = f"Sorry, I encountered an error: {str(e)}. Please try again later."
        error_response = html.Div([
            html.Div([
                html.Img(src="assets/mario_avatar.svg", className="model-avatar"),
                html.Span("Mario", className="model-name")
            ], className="model-info"),
            html.Div([
                html.Div(error_msg, className="message-text")
            ], className="message-content")
        ], className="bot-message message")
        
        # Update chat history with both user message and error response
        updated_messages = current_messages[:-1] + [error_response]
        if chat_history and len(chat_history) > 0:
            chat_history[0]["messages"] = updated_messages
            
        return (
            updated_messages,  # chat-messages.children
            chat_history,      # chat-history-store.data
            conversation_store, # conversation-store.data
            {"trigger": False, "message": ""},  # chat-trigger.data
            False              # query-running-store.data
        )


# Add callback for chat item selection
@app.callback(
    [Output("chat-messages", "children", allow_duplicate=True),
     Output("welcome-container", "className", allow_duplicate=True),
     Output("conversation-store", "data", allow_duplicate=True),
     Output("session-store", "data", allow_duplicate=True)],
    [Input({"type": "chat-item", "index": ALL}, "n_clicks")],
    [State("chat-history-store", "data"),
     State("session-store", "data")],
    prevent_initial_call=True
)
def show_chat_history(n_clicks, chat_history, session_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Check if any clicks actually happened (not just items being created)
    if not n_clicks or all(nc is None or nc == 0 for nc in n_clicks):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Get the clicked item index
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    clicked_index = json.loads(triggered_id)["index"]
    
    if not chat_history or clicked_index >= len(chat_history):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Get the conversation from history
    selected_conversation = chat_history[clicked_index]
    conversation_id = selected_conversation.get('conversation_id')
    
    logger.info(f"📖 User clicked on conversation: {conversation_id}")
    
    # Update session data and conversation store - user can continue chatting from here
    new_session_data = {"current_session": clicked_index}
    new_conversation_store = {"conversation_id": conversation_id}
    
    # Fetch messages from database if conversation_id exists
    formatted_messages = []
    if conversation_id:
        try:
            db_messages = get_conversation_messages(conversation_id)
            logger.info(f"📬 Loaded {len(db_messages)} messages for conversation {conversation_id}")
            
            # Convert database messages to HTML format
            for msg in db_messages:
                if msg['role'] == 'user':
                    formatted_messages.append(
                        html.Div([
                            html.Div(msg['content'], className="message-text")
                        ], className="user-message message")
                    )
                elif msg['role'] == 'assistant':
                    formatted_messages.append(
                        html.Div([
                            html.Div([
                                html.Img(src="assets/mario_avatar.svg", className="model-avatar"),
                                html.Span("Mario", className="model-name")
                            ], className="model-info"),
                            html.Div([
                                html.Div(msg['content'], className="message-text")
                            ], className="message-content")
                        ], className="bot-message message")
                    )
        except Exception as e:
            logger.error(f"Failed to load messages for conversation {conversation_id}: {e}")
    
    # Update chat history with loaded messages
    if formatted_messages:
        selected_conversation['messages'] = formatted_messages
        welcome_class = "welcome-container hidden"
    else:
        welcome_class = "welcome-container visible"
    
    return formatted_messages, welcome_class, new_conversation_store, new_session_data

# Modify the clientside callback to target the chat-container
app.clientside_callback(
    """
    function(children) {
        var chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        return '';
    }
    """,
    Output('dummy-output', 'children'),
    Input('chat-messages', 'children'),
    prevent_initial_call=True
)

# Modify the new chat button callback to reset session
# Commented out because sidebar-new-chat-button is removed from layout
# @app.callback(
#     [Output("welcome-container", "className", allow_duplicate=True),
#      Output("chat-messages", "children", allow_duplicate=True),
#      Output("chat-trigger", "data", allow_duplicate=True),
#      Output("query-running-store", "data", allow_duplicate=True),
#      Output("chat-history-store", "data", allow_duplicate=True),
#      Output("session-store", "data", allow_duplicate=True)],
#     [Input("sidebar-new-chat-button", "n_clicks")],
#     [State("chat-messages", "children"),
#      State("chat-trigger", "data"),
#      State("chat-history-store", "data"),
#      State("chat-list", "children"),
#      State("query-running-store", "data"),
#      State("session-store", "data")],
#     prevent_initial_call=True
# )
# def reset_to_welcome(n_clicks, chat_messages, chat_trigger, chat_history_store, 
#                     chat_list, query_running, session_data):
#     # Reset session when starting a new chat
#     new_session_data = {"current_session": None}
#     return ("welcome-container visible", [], {"trigger": False, "message": ""}, 
#             False, chat_history_store, new_session_data)

@app.callback(
    [Output("welcome-container", "className", allow_duplicate=True)],
    [Input("chat-messages", "children")],
    prevent_initial_call=True
)
def reset_query_running(chat_messages):
    # Return as a single-item list
    if chat_messages:
        return ["welcome-container hidden"]
    else:
        return ["welcome-container visible"]

# Add callback to disable input while query is running
@app.callback(
    [Output("chat-input-fixed", "disabled"),
     Output("send-button-fixed", "disabled"),
     Output("query-tooltip", "className")],
    [Input("query-running-store", "data")],
    prevent_initial_call=True
)
def disable_buttons_during_query(query_running):
    if query_running:
        return True, True, "query-tooltip visible"
    return False, False, "query-tooltip hidden"

# Callback for thumbs up/down buttons
@app.callback(
    [Output({"type": "thumbs-up-button", "index": MATCH}, "className"),
     Output({"type": "thumbs-down-button", "index": MATCH}, "className"),
     Output({"type": "feedback-toast", "index": MATCH}, "is_open"),
     Output({"type": "feedback-toast", "index": MATCH}, "children"),
     Output({"type": "comment-section", "index": MATCH}, "style"),
     Output({"type": "comment-textarea", "index": MATCH}, "style", allow_duplicate=True),
     Output({"type": "send-comment-button", "index": MATCH}, "style", allow_duplicate=True),
     Output({"type": "comment-success-message", "index": MATCH}, "style", allow_duplicate=True)],
    [Input({"type": "thumbs-up-button", "index": MATCH}, "n_clicks"),
     Input({"type": "thumbs-down-button", "index": MATCH}, "n_clicks")],
    [State({"type": "thumbs-up-button", "index": MATCH}, "className"),
     State({"type": "thumbs-down-button", "index": MATCH}, "className"),
     State({"type": "message-index", "index": MATCH}, "data"),
     State("conversation-store", "data"),
     State({"type": "thumbs-up-button", "index": MATCH}, "id")],
    prevent_initial_call=True
)
def handle_feedback(up_clicks, down_clicks, up_class, down_class, message_data, conv_store, button_id_dict):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update
    
    # Get the button that was clicked
    trigger = ctx.triggered[0]
    button_id = trigger["prop_id"].split(".")[0]
    
    try:
        logger.info(f"Feedback button clicked. Raw button_id: {button_id}")
        
        # The button_id is a string representation of a dict, we need to parse it
        try:
            import json
            button_info = json.loads(button_id.replace("'", '"'))
            is_positive = button_info["type"] == "thumbs-up-button"
            logger.info(f"Parsed button info: {button_info}, is_positive: {is_positive}")
        except Exception as e:
            logger.error(f"Error parsing button info: {str(e)}")
            raise
        
        # Get conversation ID and message index
        conversation_id = conv_store.get("conversation_id") if conv_store else None
        message_index = message_data.get("index") if message_data else None
        
        logger.info(f"Feedback data - Conversation ID: {conversation_id}, Message Index: {message_index}")
        logger.info(f"Conv store: {conv_store}")
        logger.info(f"Message data: {message_data}")
        
        # Log feedback event to database
        user_info = get_user_from_request()
        
        # Fallback for local development without auth headers
        if not user_info:
            user_info = {
                'user_id': 'local_dev_user',
                'user_email': 'dev@localhost',
                'user_name': 'Local Developer'
            }
            logger.info("Using fallback user info for local development")
        
        logger.info(f"User info: {user_info}")
        
        if user_info and conversation_id and message_index:
            try:
                log_feedback(
                    user_id=user_info['user_id'],
                    conversation_id=conversation_id,
                    message_id=message_index,
                    feedback_type='positive' if is_positive else 'negative',
                    user_email=user_info.get('user_email'),
                    user_name=user_info.get('user_name')
                )
                logger.info(f"✅ Logged feedback event: {'positive' if is_positive else 'negative'}")
                
                # Show success message and handle comment section visibility
                toast_message = "Thank you for your feedback!"
                if is_positive:
                    # Hide comment section and all its components
                    return (
                        "thumbs-up-button active", 
                        "thumbs-down-button", 
                        True, 
                        toast_message, 
                        {"display": "none"},  # Hide comment section
                        {"display": "none"},  # Hide textarea
                        {"display": "none"},  # Hide send button
                        {"display": "none"}   # Hide success message
                    )
                else:
                    # Show comment section with textarea and send button visible
                    return (
                        "thumbs-up-button", 
                        "thumbs-down-button active", 
                        True, 
                        toast_message, 
                        {"display": "block"},  # Show comment section
                        {"display": "block", "width": "100%", "minHeight": "40px", "maxHeight": "200px",
                         "padding": "10px 50px 10px 10px", "borderRadius": "8px", "border": "1px solid #d1d9e1",
                         "fontSize": "13px", "fontFamily": "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif",
                         "resize": "vertical"},  # Show textarea
                        {"display": "block", "position": "absolute", "right": "10px", "top": "10px",
                         "padding": "6px 12px", "backgroundColor": "#667eea", "color": "white",
                         "border": "none", "borderRadius": "4px", "cursor": "pointer",
                         "fontSize": "12px", "fontWeight": "600"},  # Show send button
                        {"display": "none"}  # Hide success message
                    )
                    
            except Exception as log_err:
                logger.warning(f"Failed to log feedback event: {log_err}")
                return up_class, down_class, True, "Failed to save feedback", no_update, no_update, no_update, no_update
        
        # If we get here, there was an error or missing data
        error_message = "Could not send feedback. Please try again."
        logger.warning(f"Feedback failed: {error_message}")
        return up_class, down_class, True, error_message, no_update, no_update, no_update, no_update
        
    except Exception as e:
        logger.error(f"Error in feedback handler: {str(e)}")
        return up_class, down_class, True, "An error occurred while processing feedback.", no_update, no_update, no_update, no_update
    return up_class, down_class, True, error_message if "active" not in up_class else "thumbs-up-button", no_update, no_update, no_update, no_update

# Remove the duplicate callback
# @app.callback(
#     [Output({"type": "thumbs-up-button", "index": MATCH}, "className"),
#      Output({"type": "thumbs-down-button", "index": MATCH}, "className")],
#     [Input({"type": "thumbs-up-button", "index": MATCH}, "n_clicks"),
#      Input({"type": "thumbs-down-button", "index": MATCH}, "n_clicks")],
#     [State({"type": "thumbs-up-button", "index": MATCH}, "className"),
#      State({"type": "thumbs-down-button", "index": MATCH}, "className")],
#     prevent_initial_call=True
# )
# def handle_feedback(up_clicks, down_clicks, up_class, down_class):
#     ctx = callback_context
#     if not ctx.triggered:
#         return dash.no_update, dash.no_update
    
#     trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
#     button_type = json.loads(trigger_id)["type"]
    
#     if button_type == "thumbs-up-button":
#         new_up_class = "thumbs-up-button active" if "active" not in up_class else "thumbs-up-button"
#         new_down_class = "thumbs-down-button"
#     else:
#         new_up_class = "thumbs-up-button"
#         new_down_class = "thumbs-down-button active" if "active" not in down_class else "thumbs-down-button"
    
#     return new_up_class, new_down_class

# Add callback for toggling SQL query visibility
@app.callback(
    [Output({"type": "query-code", "index": MATCH}, "className"),
     Output({"type": "toggle-text", "index": MATCH}, "children")],
    [Input({"type": "toggle-query", "index": MATCH}, "n_clicks")],
    prevent_initial_call=True
)
def toggle_query_visibility(n_clicks):
    if n_clicks % 2 == 1:
        return "query-code-container visible", "Hide code"
    return "query-code-container hidden", "Show code"

# Add callbacks for welcome text customization
@app.callback(
    [Output("edit-welcome-modal", "is_open", allow_duplicate=True),
     Output("welcome-title-input", "value"),
     Output("welcome-description-input", "value"),
     Output("suggestion-1-input", "value"),
     Output("suggestion-2-input", "value"),
     Output("suggestion-3-input", "value"),
     Output("suggestion-4-input", "value")],
    [Input("edit-welcome-button", "n_clicks")],
    [State("welcome-title", "children"),
     State("welcome-description", "children"),
     State("suggestion-1-text", "children"),
     State("suggestion-2-text", "children"),
     State("suggestion-3-text", "children"),
     State("suggestion-4-text", "children")],
    prevent_initial_call=True
)
def open_modal(n_clicks, current_title, current_description, s1, s2, s3, s4):
    if not n_clicks:
        return [no_update] * 7
    return True, current_title, current_description, s1, s2, s3, s4

@app.callback(
    [Output("welcome-title", "children", allow_duplicate=True),
     Output("welcome-description", "children", allow_duplicate=True),
     Output("suggestion-1-text", "children", allow_duplicate=True),
     Output("suggestion-2-text", "children", allow_duplicate=True),
     Output("suggestion-3-text", "children", allow_duplicate=True),
     Output("suggestion-4-text", "children", allow_duplicate=True),
     Output("edit-welcome-modal", "is_open", allow_duplicate=True)],
    [Input("save-welcome-text", "n_clicks"),
     Input("close-modal", "n_clicks")],
    [State("welcome-title-input", "value"),
     State("welcome-description-input", "value"),
     State("suggestion-1-input", "value"),
     State("suggestion-2-input", "value"),
     State("suggestion-3-input", "value"),
     State("suggestion-4-input", "value"),
     State("welcome-title", "children"),
     State("welcome-description", "children"),
     State("suggestion-1-text", "children"),
     State("suggestion-2-text", "children"),
     State("suggestion-3-text", "children"),
     State("suggestion-4-text", "children")],
    prevent_initial_call=True
)
def handle_modal_actions(save_clicks, close_clicks,
                        new_title, new_description, s1, s2, s3, s4,
                        current_title, current_description,
                        current_s1, current_s2, current_s3, current_s4):
    ctx = callback_context
    if not ctx.triggered:
        return [no_update] * 7

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger_id == "close-modal":
        return [current_title, current_description, 
                current_s1, current_s2, current_s3, current_s4, False]
    elif trigger_id == "save-welcome-text":
        # Save the changes
        title = new_title if new_title else DEFAULT_WELCOME_TITLE
        description = new_description if new_description else DEFAULT_WELCOME_DESCRIPTION
        suggestions = [
            s1 if s1 else DEFAULT_SUGGESTIONS[0],
            s2 if s2 else DEFAULT_SUGGESTIONS[1],
            s3 if s3 else DEFAULT_SUGGESTIONS[2],
            s4 if s4 else DEFAULT_SUGGESTIONS[3]
        ]
        return [title, description, *suggestions, False]

    return [no_update] * 7

# Clientside callback to show loading indicator immediately when button is clicked
app.clientside_callback(
    """
    function(n_clicks, btn_id) {
        if (n_clicks) {
            // Get the index from the button ID
            const index = btn_id.index;
            // Find the specific output div for this button using the index
            const outputDivs = document.querySelectorAll('[id*="insight-output"]');
            for (let div of outputDivs) {
                if (div.id.includes(index)) {
                    const loader = div.querySelector('.insight-loading-indicator');
                    if (loader) {
                        loader.style.display = 'flex';
                        break;
                    }
                }
            }
        }
        return window.dash_clientside.no_update;
    }
    """,
    Output({"type": "insight-button", "index": dash.dependencies.MATCH}, "n_clicks", allow_duplicate=True),
    Input({"type": "insight-button", "index": dash.dependencies.MATCH}, "n_clicks"),
    State({"type": "insight-button", "index": dash.dependencies.MATCH}, "id"),
    prevent_initial_call=True
)

# Add callback for insight button
@app.callback(
    Output({"type": "insight-output", "index": dash.dependencies.MATCH}, "children"),
    Input({"type": "insight-button", "index": dash.dependencies.MATCH}, "n_clicks"),
    State({"type": "insight-button", "index": dash.dependencies.MATCH}, "id"),
    State("chat-history-store", "data"),
    prevent_initial_call=True
)
def generate_insights(n_clicks, btn_id, chat_history):
    if not n_clicks:
        return None  # Don't show anything before click
    table_id = btn_id["index"]
    # Retrieve the DataFrame from chat_history
    df = None
    if chat_history and len(chat_history) > 0:
        df_json = chat_history[0].get('dataframes', {}).get(table_id)
        if df_json:
            df = pd.read_json(df_json, orient='split')
    if df is None:
        return None
    insights = call_llm_for_insights(df)
    return html.Div([
        # Close button
        html.Button(
            "✕",
            id={"type": "close-insight", "index": table_id},
            className="close-insight-button",
            style={
                "position": "absolute",
                "top": "8px",
                "right": "8px",
                "background": "transparent",
                "border": "none",
                "fontSize": "18px",
                "cursor": "pointer",
                "color": "#666666",
                "padding": "4px 8px"
            },
            n_clicks=0
        ),
        # Insights content
        dcc.Markdown(insights)
    ],
        style={
            "marginTop": "12px",
            "background": "#f4f4f4",
            "padding": "16px",
            "borderRadius": "4px",
            "position": "relative"
        },
        className="insight-output"
    )

# Callback to close/hide insights when X is clicked
@app.callback(
    Output({"type": "insight-output", "index": dash.dependencies.MATCH}, "children", allow_duplicate=True),
    Input({"type": "close-insight", "index": dash.dependencies.MATCH}, "n_clicks"),
    prevent_initial_call=True
)
def close_insights(n_clicks):
    if n_clicks:
        # Return the loading indicator structure (hidden) so it can be shown again on next click
        return [
            html.Div([
                html.Span(className="spinner"),
                html.Div([
                    html.Span("Studying data...", className="rotating-text"),
                    html.Span("Talking to LLM...", className="rotating-text"),
                    html.Span("Summarizing key points...", className="rotating-text")
                ], className="rotating-text-container")
            ], className="insight-loading-indicator", style={"display": "none"})
        ]
    return no_update

# Callback to save comment when Send button is clicked
@app.callback(
    [Output({"type": "comment-textarea", "index": MATCH}, "style"),
     Output({"type": "send-comment-button", "index": MATCH}, "style"),
     Output({"type": "comment-success-message", "index": MATCH}, "style"),
     Output({"type": "success-message-timer", "index": MATCH}, "disabled")],
    Input({"type": "send-comment-button", "index": MATCH}, "n_clicks"),
    [State({"type": "comment-textarea", "index": MATCH}, "value"),
     State({"type": "message-index", "index": MATCH}, "data"),
     State("conversation-store", "data")],
    prevent_initial_call=True
)
def save_user_comment(n_clicks, comment_text, message_data, conv_store):
    if not n_clicks or not comment_text or not comment_text.strip():
        return no_update, no_update, no_update, no_update
    
    try:
        # Get user info and conversation details
        user_info = get_user_from_request()
        
        # Fallback for local development without auth headers
        if not user_info:
            user_info = {
                'user_id': 'local_dev_user',
                'user_email': 'dev@localhost',
                'user_name': 'Local Developer'
            }
            logger.info("Using fallback user info for local development")
        
        conversation_id = conv_store.get("conversation_id") if conv_store else None
        message_id = message_data.get("index") if message_data else None
        
        logger.info(f"Comment save - User: {user_info.get('user_id')}, Conv: {conversation_id}, Msg: {message_id}")
        
        if user_info and conversation_id and message_id:
            from event_logger import save_comment
            
            # Save comment to database
            success = save_comment(
                user_id=user_info['user_id'],
                conversation_id=conversation_id,
                message_id=message_id,
                comment=comment_text.strip()
            )
            
            if success:
                logger.info(f"✅ Saved comment for message {message_id}")
                # Hide textarea and send button, show success message, enable timer
                return (
                    {"display": "none"},  # Hide textarea
                    {"display": "none"},  # Hide send button
                    {"display": "block", "marginTop": "8px", "padding": "8px 12px",
                     "backgroundColor": "#d4edda", "color": "#155724",
                     "border": "1px solid #c3e6cb", "borderRadius": "4px", "fontSize": "13px"},  # Show success message
                    False  # Enable timer to hide message after 2 seconds
                )
            else:
                logger.warning("Failed to save comment")
                return no_update, no_update, no_update, no_update
        else:
            logger.warning("Missing user info, conversation_id, or message_id")
            return no_update, no_update, no_update, no_update
            
    except Exception as e:
        logger.error(f"Error saving comment: {str(e)}")
        return no_update, no_update, no_update, no_update

# Callback to hide success message after timer expires
@app.callback(
    Output({"type": "comment-success-message", "index": MATCH}, "style", allow_duplicate=True),
    Input({"type": "success-message-timer", "index": MATCH}, "n_intervals"),
    prevent_initial_call=True
)
def hide_success_message(n_intervals):
    if n_intervals and n_intervals > 0:
        return {"display": "none"}
    return no_update

# ============================================================================
# FAVORITES CALLBACKS
# ============================================================================

# Callback for star button - show favorites section and synthesize question
@app.callback(
    [Output({"type": "favorites-section", "index": MATCH}, "style"),
     Output({"type": "favorite-textarea", "index": MATCH}, "value"),
     Output({"type": "star-button", "index": MATCH}, "children")],
    Input({"type": "star-button", "index": MATCH}, "n_clicks"),
    [State({"type": "star-sql-store", "index": MATCH}, "data"),
     State({"type": "favorites-section", "index": MATCH}, "style")],
    prevent_initial_call=True
)
def toggle_favorites_section(n_clicks, sql_query, current_style):
    logger.info(f"⭐ toggle_favorites_section called: n_clicks={n_clicks}, has sql_query={sql_query is not None}")
    
    if not n_clicks:
        return no_update, no_update, no_update
    
    # Check if SQL query exists
    if not sql_query:
        logger.warning("Star button clicked but no SQL query found in store")
        return no_update, no_update, no_update
    
    # Toggle visibility
    is_hidden = current_style.get("display") == "none"
    
    if is_hidden:
        # Show section and synthesize question
        logger.info(f"Star button clicked, synthesizing question from SQL")
        try:
            synthesized_question = synthesize_question_from_sql(sql_query)
            return {"display": "block", "marginTop": "12px"}, synthesized_question, "★"
        except Exception as e:
            logger.error(f"Error synthesizing question: {e}")
            return {"display": "block", "marginTop": "12px"}, "Error generating question. Please edit manually.", "★"
    else:
        # Hide section
        return {"display": "none", "marginTop": "12px"}, "", "☆"

# Callback for save favorite button
@app.callback(
    [Output({"type": "success-toast", "index": MATCH}, "style"),
     Output({"type": "favorites-section", "index": MATCH}, "style", allow_duplicate=True),
     Output({"type": "star-button", "index": MATCH}, "children", allow_duplicate=True)],
    Input({"type": "save-favorite-button", "index": MATCH}, "n_clicks"),
    [State({"type": "favorite-textarea", "index": MATCH}, "value"),
     State({"type": "star-sql-store", "index": MATCH}, "data")],
    prevent_initial_call=True
)
def save_favorite_to_db(n_clicks, question, sql_query):
    if not n_clicks or not question or not sql_query:
        return no_update, no_update, no_update
    
    # Get user info from request headers (same pattern as other callbacks)
    user_info = get_user_from_request()
    
    # Fallback for local development without auth headers
    if not user_info:
        user_info = {
            'user_id': 'local_dev_user',
            'user_email': 'dev@localhost',
            'user_name': 'Local Developer'
        }
        logger.info("Using fallback user info for local development")
    
    logger.info(f"💾 Saving favorite for user {user_info.get('user_id')}")
    
    # Save to database
    from event_logger import save_favorite
    success = save_favorite(
        user_id=user_info.get("user_id"),
        user_email=user_info.get("user_email"),
        question=question,
        sql_query=sql_query
    )
    
    if success:
        logger.info("✅ Favorite saved successfully, showing toast with close button")
        
        # Show success toast (with flex display for button alignment), hide favorites section, fill star
        return (
            {"display": "flex", "backgroundColor": "#FFF4CC", "color": "#000", "padding": "12px 16px", 
             "borderRadius": "8px", "marginTop": "12px", "fontSize": "13px", "fontWeight": "500", 
             "border": "1px solid #FFD700", "alignItems": "center", "justifyContent": "space-between"},
            {"display": "none", "marginTop": "12px"},
            "★"
        )
    else:
        logger.error("Failed to save favorite")
        return no_update, no_update, no_update

# Callback to refresh favorites after saving
@app.callback(
    Output("favorites-store", "data", allow_duplicate=True),
    Input({"type": "success-toast", "index": ALL}, "style"),
    prevent_initial_call=True
)
def refresh_favorites_after_save(toast_styles):
    """Refresh favorites list when a success toast is shown"""
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update
    
    # Check if any toast was just shown (display: flex)
    for style in toast_styles:
        if style and style.get("display") == "flex":
            user_info = get_user_from_request()
            
            # Fallback for local development
            if not user_info:
                user_info = {
                    'user_id': 'local_dev_user',
                    'user_email': 'dev@localhost',
                    'user_name': 'Local Developer'
                }
            
            updated_favorites = get_user_favorites(user_info.get("user_id"))
            logger.info(f"🔄 Refreshed favorites list: {len(updated_favorites)} items")
            return updated_favorites
    
    return no_update

# Callback to hide success toast when close button is clicked
@app.callback(
    Output({"type": "success-toast", "index": MATCH}, "style", allow_duplicate=True),
    Input({"type": "close-toast", "index": MATCH}, "n_clicks"),
    prevent_initial_call=True
)
def close_success_toast(n_clicks):
    if n_clicks:
        return {"display": "none"}
    return no_update

# Callback to handle clicking a favorite (add to chat)
@app.callback(
    [Output("chat-messages", "children", allow_duplicate=True),
     Output("chat-input-fixed", "value", allow_duplicate=True),
     Output("welcome-container", "className", allow_duplicate=True),
     Output("chat-trigger", "data", allow_duplicate=True),
     Output("query-running-store", "data", allow_duplicate=True),
     Output("chat-history-store", "data", allow_duplicate=True),
     Output("session-store", "data", allow_duplicate=True)],
    Input({"type": "favorite-item", "index": ALL}, "n_clicks"),
    [State("favorites-store", "data"),
     State("chat-messages", "children"),
     State("welcome-container", "className"),
     State("chat-history-store", "data"),
     State("session-store", "data")],
    prevent_initial_call=True
)
def click_favorite(n_clicks_list, favorites, current_messages, welcome_class, chat_history, session_data):
    """When a favorite is clicked, add it to chat and trigger response (same as suggestion buttons)"""
    if not any(n_clicks_list) or not favorites:
        return [no_update] * 7
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return [no_update] * 7
    
    # Get which favorite was clicked
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    trigger_dict = json.loads(trigger_id)
    favorite_id = trigger_dict["index"]
    
    # Find the favorite
    favorite = next((f for f in favorites if f['id'] == favorite_id), None)
    if not favorite:
        return [no_update] * 7
    
    user_input = favorite['question']
    logger.info(f"⭐ Clicked favorite: {user_input}")
    
    # Create user message
    user_message = html.Div([
        html.Div(user_input, className="message-text")
    ], className="user-message message")
    
    # Add the user message to the chat
    updated_messages = current_messages + [user_message] if current_messages else [user_message]
    
    # Add thinking indicator
    thinking_indicator = html.Div([
        html.Div([
            html.Span(className="spinner"),
            html.Span("Thinking...")
        ], className="thinking-indicator")
    ], className="bot-message message")
    
    updated_messages.append(thinking_indicator)
    
    # Handle session management
    if session_data["current_session"] is None:
        session_data = {"current_session": len(chat_history) if chat_history else 0}
    
    current_session = session_data["current_session"]
    
    # Update chat history
    if chat_history is None:
        chat_history = []
    
    if current_session < len(chat_history):
        # Update existing conversation
        chat_history[current_session]["messages"] = updated_messages
        # Update title if this is first message in conversation
        if not chat_history[current_session].get("title") or chat_history[current_session].get("title") == "New conversation":
            chat_history[current_session]["title"] = user_input[:50] + '...' if len(user_input) > 50 else user_input
    else:
        # Create new conversation with standardized structure
        chat_history.insert(0, {
            "conversation_id": None,  # Will be set after API response
            "title": user_input[:50] + '...' if len(user_input) > 50 else user_input,
            "messages": updated_messages,
            "message_count": 1
        })
    
    return (
        updated_messages,
        "",  # Clear input field
        "welcome-container hidden",  # Hide welcome
        {"trigger": True, "message": user_input},  # Trigger bot response
        True,  # Set query running
        chat_history,  # Update chat history
        session_data  # Update session
    )

# Callback to handle delete button click (show confirm buttons)
@app.callback(
    Output({"type": "favorite-delete", "index": MATCH}, "style"),
    Output({"type": "favorite-confirm-container", "index": MATCH}, "style"),
    Input({"type": "favorite-delete", "index": MATCH}, "n_clicks"),
    prevent_initial_call=True
)
def show_confirm_buttons(n_clicks):
    """Hide delete button and show confirm/cancel buttons"""
    if n_clicks:
        return {"display": "none"}, {"display": "flex"}
    return no_update, no_update

# Callback to handle cancel button (hide confirm, show delete)
@app.callback(
    Output({"type": "favorite-delete", "index": MATCH}, "style", allow_duplicate=True),
    Output({"type": "favorite-confirm-container", "index": MATCH}, "style", allow_duplicate=True),
    Input({"type": "favorite-confirm-no", "index": MATCH}, "n_clicks"),
    prevent_initial_call=True
)
def cancel_delete(n_clicks):
    """Hide confirm buttons and show delete button again"""
    if n_clicks:
        return {"display": "flex"}, {"display": "none"}
    return no_update, no_update

# Callback to actually delete the favorite when confirmed
@app.callback(
    Output("favorites-store", "data", allow_duplicate=True),
    Input({"type": "favorite-confirm-yes", "index": ALL}, "n_clicks"),
    State("favorites-store", "data"),
    prevent_initial_call=True
)
def delete_favorite(n_clicks_list, favorites):
    """Delete favorite when confirm (tick) button is clicked"""
    if not any(n_clicks_list) or not favorites:
        return no_update
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return no_update
    
    # Get which confirm button was clicked
    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    trigger_dict = json.loads(trigger_id)
    favorite_id = trigger_dict["index"]
    
    user_info = get_user_from_request()
    
    # Fallback for local development
    if not user_info:
        user_info = {
            'user_id': 'local_dev_user',
            'user_email': 'dev@localhost',
            'user_name': 'Local Developer'
        }
    
    success = delete_user_favorite(favorite_id, user_info['user_id'])
    if success:
        logger.info(f"🗑️ Deleted favorite {favorite_id}")
        # Remove from favorites list
        updated_favorites = [f for f in favorites if f['id'] != favorite_id]
        return updated_favorites
    
    return no_update

# ============================================================================
# STATS DASHBOARD CALLBACKS
# ============================================================================

from stats_page import (
    create_metric_card, create_nps_display,
    create_unique_visitors_chart, create_activity_by_hour_chart,
    create_feedback_trends_chart, create_retention_chart,
    create_top_users_table, create_popular_questions_list,
    create_conversation_trends_chart
)

@app.callback(
    Output('stats-refresh-trigger', 'data'),
    [Input('stats-refresh-btn', 'n_clicks'),
     Input('stats-interval', 'n_intervals')]
)
def trigger_stats_refresh(n_clicks, n_intervals):
    return (n_clicks or 0) + n_intervals

@app.callback(
    Output('key-metrics-cards', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_key_metrics(trigger):
    try:
        engagement = stats_queries.get_engagement_metrics()
        conversation = stats_queries.get_conversation_metrics()
        nps = stats_queries.get_nps_score()
        
        cards = [
            create_metric_card("Total Users", engagement.get('total_users', 0), "Unique visitors", "👥"),
            create_metric_card("Conversations Started", engagement.get('total_conversations', 0), 
                             f"Avg {engagement.get('avg_messages_per_conversation', 0)} msgs/conv", "💬"),
            create_metric_card("Total Messages", engagement.get('total_messages', 0), "User interactions", "📨"),
            create_metric_card("NPS Score", nps.get('nps', 0), f"{nps.get('total', 0)} feedback responses", "⭐"),
            create_metric_card("Feedback Rate", f"{conversation.get('feedback_rate', 0)}%", 
                             f"{conversation.get('conversations_with_feedback', 0)} conversations rated", "📊"),
            create_metric_card("Avg Messages/Conv", conversation.get('avg_messages_per_conversation', 0), 
                             f"Median: {conversation.get('median_messages', 0)}", "📈")
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
    try:
        data = stats_queries.get_unique_visitors('daily')
        return create_unique_visitors_chart(data['data'])
    except Exception as e:
        logger.error(f"Error updating visitors chart: {e}")
        return {}

@app.callback(
    Output('activity-by-hour-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_activity_chart(trigger):
    try:
        data = stats_queries.get_activity_by_hour()
        return create_activity_by_hour_chart(data)
    except Exception as e:
        logger.error(f"Error updating activity chart: {e}")
        return {}

@app.callback(
    Output('conversation-trends-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_conversation_trends(trigger):
    try:
        engagement = stats_queries.get_engagement_metrics()
        return create_conversation_trends_chart(engagement)
    except Exception as e:
        logger.error(f"Error updating conversation trends: {e}")
        return {}

@app.callback(
    Output('nps-score-display', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_nps_display(trigger):
    try:
        nps_data = stats_queries.get_nps_score()
        return create_nps_display(nps_data)
    except Exception as e:
        logger.error(f"Error updating NPS display: {e}")
        return html.P("Error loading NPS data")

@app.callback(
    Output('feedback-trends-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_feedback_trends(trigger):
    try:
        data = stats_queries.get_feedback_over_time()
        return create_feedback_trends_chart(data)
    except Exception as e:
        logger.error(f"Error updating feedback trends: {e}")
        return {}

@app.callback(
    Output('top-users-table', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_top_users(trigger):
    try:
        users = stats_queries.get_top_users(limit=10)
        return create_top_users_table(users)
    except Exception as e:
        logger.error(f"Error updating top users: {e}")
        return html.P("Error loading users data")

@app.callback(
    Output('popular-questions-list', 'children'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_popular_questions(trigger):
    try:
        questions = stats_queries.get_popular_questions()
        return create_popular_questions_list(questions)
    except Exception as e:
        logger.error(f"Error updating popular questions: {e}")
        return html.P("Error loading questions data")

@app.callback(
    Output('retention-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data')]
)
def update_retention_chart(trigger):
    try:
        data = stats_queries.get_user_retention()
        return create_retention_chart(data)
    except Exception as e:
        logger.error(f"Error updating retention chart: {e}")
        return {}

# Callbacks for SQL Usage Analytics
@app.callback(
    Output('table-usage-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data'),
     Input('stats-time-filter', 'value')]
)
def update_table_usage_chart(trigger, time_filter):
    try:
        from event_logger import get_sql_usage_analytics
        from stats_page import create_table_usage_chart
        
        # Map time filter to days
        days_map = {'7d': 7, '30d': 30, '90d': 90, 'all': 0}
        days = days_map.get(time_filter, 30)
        
        analytics = get_sql_usage_analytics(days)
        return create_table_usage_chart(analytics['tables'])
    except Exception as e:
        logger.error(f"Error updating table usage chart: {e}")
        return {}

@app.callback(
    Output('column-usage-chart', 'figure'),
    [Input('stats-refresh-trigger', 'data'),
     Input('stats-time-filter', 'value')]
)
def update_column_usage_chart(trigger, time_filter):
    try:
        from event_logger import get_sql_usage_analytics
        from stats_page import create_column_usage_chart
        
        # Map time filter to days
        days_map = {'7d': 7, '30d': 30, '90d': 90, 'all': 0}
        days = days_map.get(time_filter, 30)
        
        analytics = get_sql_usage_analytics(days)
        return create_column_usage_chart(analytics['columns'])
    except Exception as e:
        logger.error(f"Error updating column usage chart: {e}")
        return {}

@app.callback(
    Output('table-column-details', 'children'),
    [Input('stats-refresh-trigger', 'data'),
     Input('stats-time-filter', 'value')]
)
def update_table_column_details(trigger, time_filter):
    try:
        from event_logger import get_sql_usage_analytics
        from stats_page import create_table_column_details
        
        # Map time filter to days
        days_map = {'7d': 7, '30d': 30, '90d': 90, 'all': 0}
        days = days_map.get(time_filter, 30)
        
        analytics = get_sql_usage_analytics(days)
        return create_table_column_details(analytics['table_columns'])
    except Exception as e:
        logger.error(f"Error updating table column details: {e}")
        return html.P("Error loading data")

# Callback to handle export button clicks
@app.callback(
    [Output("download-dataframe-csv", "data"),
     Output("export-clicks-tracker", "data")],
    [Input({"type": "export-button", "index": ALL}, "n_clicks")],
    [State("chat-history-store", "data"),
     State("export-clicks-tracker", "data")],
    prevent_initial_call=True
)
def export_table_to_csv(n_clicks_list, chat_history, clicks_tracker):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update
    
    # Get the trigger info
    trigger = ctx.triggered[0]
    prop_id = trigger["prop_id"]
    
    # Only process if this is actually from a button click
    if not prop_id.endswith(".n_clicks"):
        return no_update, no_update
    
    trigger_value = trigger["value"]
    
    # Only process if button was actually clicked (value must be positive)
    if not trigger_value or trigger_value <= 0:
        return no_update, no_update
    
    button_id = prop_id.split(".")[0]
    
    # Check if we've already processed this exact click count for this button
    clicks_tracker = clicks_tracker or {}
    if button_id in clicks_tracker and clicks_tracker[button_id] >= trigger_value:
        return no_update, no_update
    
    # Update tracker to record this click count
    clicks_tracker[button_id] = trigger_value
    
    try:
        import json
        button_info = json.loads(button_id.replace("'", '"'))
        table_index = button_info["index"]
        
        # Get the DataFrame from chat_history
        if chat_history and len(chat_history) > 0:
            dataframes = chat_history[0].get('dataframes', {})
            if table_index in dataframes:
                df_json = dataframes[table_index]
                df = pd.read_json(df_json, orient='split')
                
                # Return CSV download with updated tracker
                return dcc.send_data_frame(df.to_csv, "export.csv", index=False), clicks_tracker
    except Exception as e:
        logger.error(f"Error exporting table: {e}")
    
    return no_update, no_update


# Clientside callback for downloading chart as PNG
app.clientside_callback(
    """
    function(n_clicks, button_id) {
        if (!n_clicks) return window.dash_clientside.no_update;
        
        // Extract chart ID from button ID
        const chartId = button_id.index;
        console.log('Button clicked for chart:', chartId);
        
        // Find the dcc.Graph element by ID
        const chartElement = document.getElementById(chartId);
        
        if (!chartElement) {
            console.error('Chart element not found:', chartId);
            return window.dash_clientside.no_update;
        }
        
        console.log('Chart element found:', chartElement);
        
        // The dcc.Graph component contains the Plotly plot
        // Try to find the plotly div directly
        let plotlyDiv = chartElement;
        
        // If chartElement is not the plotly div itself, look for it inside
        if (!chartElement.data && !chartElement.layout) {
            plotlyDiv = chartElement.querySelector('.js-plotly-plot');
        }
        
        if (plotlyDiv && (plotlyDiv.data || plotlyDiv.layout)) {
            const timestamp = Date.now();
            const filename = 'mario_chart_' + timestamp;
            
            console.log('Downloading chart as:', filename);
            
            // Use Plotly's toImage to download
            Plotly.toImage(plotlyDiv, {
                format: 'png',
                width: 1200,
                height: 800,
                filename: filename
            }).then(function(url) {
                // Create download link
                const a = document.createElement('a');
                a.href = url;
                a.download = filename + '.png';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                console.log('Download triggered');
            }).catch(function(err) {
                console.error('Download failed:', err);
            });
        } else {
            console.error('Plotly div not found or invalid');
        }
        
        return window.dash_clientside.no_update;
    }
    """,
    Output({"type": "download-chart", "index": MATCH}, "n_clicks"),
    Input({"type": "download-chart", "index": MATCH}, "n_clicks"),
    State({"type": "download-chart", "index": MATCH}, "id"),
    prevent_initial_call=True
)


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8080)