import requests
import threading
from datetime import datetime, timedelta
import logging
import os
from flask import has_request_context, request
from dotenv import load_dotenv
load_dotenv(override=True)

logger = logging.getLogger(__name__)

class TokenMinter:
    """
    A class to handle user-specific token management for Databricks Apps.
    When deployed as a Databricks App with require_user_authentication: true,
    the user's credentials are automatically available via the Databricks SDK.
    """
    def __init__(self, user_token: str = None):
        """
        Initialize with a user-specific token.
        
        Args:
            user_token: Optional user's Databricks authentication token.
                       If None, will use Databricks SDK authentication.
        """
        self.user_token = user_token
        self.lock = threading.RLock()
        self._workspace_client = None
    
    def get_token(self) -> str:
        """
        Get the user's authentication token.
        For Databricks Apps with require_user_authentication: true,
        this automatically uses the authenticated user's credentials.
        
        Returns:
            str: The user's valid authentication token
        """
        with self.lock:
            # If token was provided at initialization, use it
            if self.user_token:
                return self.user_token
            
            # Check for Databricks Apps environment variable (set by platform)
            apps_token = os.getenv('DATABRICKS_TOKEN') or os.getenv('DB_TOKEN')
            if apps_token:
                logger.info("Using token from Databricks Apps environment")
                return apps_token
            
            # Try to use Databricks SDK with default credentials
            try:
                from databricks.sdk import WorkspaceClient
                from databricks.sdk.core import Config
                
                if self._workspace_client is None:
                    # In Databricks Apps, credentials are auto-configured
                    self._workspace_client = WorkspaceClient()
                
                # Try to get token from config
                if hasattr(self._workspace_client.config, 'token') and self._workspace_client.config.token:
                    logger.info("Using token from WorkspaceClient config")
                    return self._workspace_client.config.token
                
                # Try to authenticate and get token
                if hasattr(self._workspace_client.config, 'authenticate'):
                    self._workspace_client.config.authenticate()
                    if hasattr(self._workspace_client.config, 'token') and self._workspace_client.config.token:
                        logger.info("Using token from authenticated WorkspaceClient")
                        return self._workspace_client.config.token
                
                # For service principals, the SDK might use other auth methods
                # Try to make a simple API call to verify authentication works
                try:
                    current_user = self._workspace_client.current_user.me()
                    # If we got here, auth is working even if we don't have direct token access
                    # For Databricks Apps, we might need to use the SDK directly
                    logger.info("WorkspaceClient authenticated successfully")
                    # Return a placeholder - the SDK will handle auth internally
                    return "DATABRICKS_SDK_AUTH"
                except Exception as auth_error:
                    logger.debug(f"Could not verify authentication: {auth_error}")
                        
            except Exception as e:
                logger.warning(f"Could not get token from Databricks SDK: {e}")
            
            raise ValueError(
                "No authentication token available. "
                "Ensure the app is deployed as a Databricks App with require_user_authentication: true, "
                "or set DATABRICKS_TOKEN environment variable for local development."
            )
    
    
    def get_user_id(self) -> str:
        """
        Get the authenticated user's ID.
        
        Returns:
            str: User ID or email
        """
        try:
            from databricks.sdk import WorkspaceClient
            if self._workspace_client is None:
                self._workspace_client = WorkspaceClient()
            
            # Get current user information
            current_user = self._workspace_client.current_user.me()
            return current_user.user_name or current_user.id or 'unknown'
        except Exception as e:
            logger.warning(f"Could not get user ID: {e}")
            
            # Fallback to request headers
            if has_request_context():
                return request.headers.get('X-Databricks-User-Id', 'unknown')
            
            return 'unknown'


def get_user_token_minter() -> TokenMinter:
    """
    Get a TokenMinter instance for the current authenticated user.
    
    Returns:
        TokenMinter: A token minter for the current user
    """
    return TokenMinter()

