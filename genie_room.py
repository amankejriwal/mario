import os
import time
import json
import logging
import backoff
import requests
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, asdict
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from databricks.sdk.core import DatabricksError
import uuid
from token_minter import TokenMinter, get_user_token_minter
from dotenv import load_dotenv
from event_logger import log_start_conversation, log_send_message, log_sql_response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Load environment variables
SPACE_ID = os.environ.get("SPACE_ID")
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST")

# Initialize a global WorkspaceClient for authentication and user tracking
try:
    ws = WorkspaceClient()
    current_user = ws.current_user.me()
except Exception as e:
    logger.error(f"Failed to initialize WorkspaceClient: {e}")
    ws = None
    current_user = None


class GenieClient:
    def __init__(self, host: str, space_id: str, token_minter: TokenMinter = None):
        self.host = host
        self.space_id = space_id
        self.token_minter = token_minter or get_user_token_minter()
        self.base_url = f"https://{host}/api/2.0/genie/spaces/{space_id}"
        
        # Try to use WorkspaceClient for authenticated requests
        self._use_sdk_auth = False
        self._user_info = None
        
        try:
            from databricks.sdk import WorkspaceClient
            self._workspace_client = WorkspaceClient()
            self._use_sdk_auth = True
            
            # Capture and log user information
            try:
                user = self._workspace_client.current_user.me()
                self._user_info = {
                    "user_name": user.user_name,
                    "user_id": user.id,
                    "email": user.emails[0].value if user.emails else None,
                    "display_name": user.display_name
                }
                logger.info(f"🔐 SDK Auth: User '{self._user_info['user_name']}' (ID: {self._user_info['user_id']})")
                
                # Log token info if available (for debugging)
                if hasattr(self._workspace_client.config, 'token'):
                    token = self._workspace_client.config.token
                    if token and token != "DATABRICKS_SDK_AUTH":
                        # Log only first/last few chars for security
                        masked_token = f"{token[:8]}...{token[-8:]}" if len(token) > 16 else "[REDACTED]"
                        logger.info(f"🔑 Token preview: {masked_token}")
                
            except Exception as user_err:
                logger.warning(f"Could not fetch user info: {user_err}")
            
            logger.info("✅ Using Databricks SDK authentication for API calls")
            
        except Exception as e:
            logger.debug(f"Could not initialize WorkspaceClient, using token-based auth: {e}")
            self._workspace_client = None
        
        self.update_headers()

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get the current authenticated user's information"""
        return self._user_info

    def update_headers(self) -> None:
        """Update headers - SDK handles auth internally"""
        if self._use_sdk_auth:
            # SDK handles authentication internally
            self.headers = {"Content-Type": "application/json"}
        else:
            # Fallback to token-based auth
            token = self.token_minter.get_token()
            if token == "DATABRICKS_SDK_AUTH":
                self.headers = {"Content-Type": "application/json"}
            else:
                self.headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }

    def _make_authenticated_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated API request"""
        url = f"{self.base_url}{endpoint}"

        if self._use_sdk_auth and self._workspace_client:
            headers = kwargs.get('headers', {})
            headers.update(self.headers)
            api_client = self._workspace_client.api_client
            if method.upper() == 'POST':
                body_data = kwargs.get('json', {})
                return api_client.do('POST', endpoint, body=json.dumps(body_data), headers=headers)
            elif method.upper() == 'GET':
                return api_client.do('GET', endpoint, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
        else:
            self.update_headers()
            kwargs['headers'] = self.headers
            return requests.request(method, url, **kwargs)

    @backoff.on_exception(
        backoff.expo, Exception, max_tries=5, factor=2, jitter=backoff.full_jitter,
        on_backoff=lambda d: logger.warning(
            f"API request failed. Retrying in {d['wait']:.2f}s (attempt {d['tries']})"
        )
    )
    def start_conversation(self, question: str) -> Dict[str, Any]:
        """Start a new conversation with Genie"""
        payload = {"content": question}
        url = f"/api/2.0/genie/spaces/{self.space_id}/start-conversation"
        response = self._workspace_client.api_client.do(
            'POST', url, body=payload, headers={'Content-Type': 'application/json'}
        )
        logger.info(f"Response: {response}")
        return response

    @backoff.on_exception(backoff.expo, Exception, max_tries=5, factor=2, jitter=backoff.full_jitter)
    def send_message(self, conversation_id: str, message: str) -> Dict[str, Any]:
        """Send a follow-up message"""
        payload = {"content": message}
        url = f"/api/2.0/genie/spaces/{self.space_id}/conversations/{conversation_id}/messages"
        response = self._workspace_client.api_client.do(
            'POST', url, body=payload, headers={'Content-Type': 'application/json'}
        )
        return response

    @backoff.on_exception(backoff.expo, Exception, max_tries=5, factor=2, jitter=backoff.full_jitter)
    def get_message(self, conversation_id: str, message_id: str) -> Dict[str, Any]:
        """Fetch details of a specific Genie message"""
        url = f"/api/2.0/genie/spaces/{self.space_id}/conversations/{conversation_id}/messages/{message_id}"
        response = self._workspace_client.api_client.do('GET', url)
        return response

    @backoff.on_exception(backoff.expo, Exception, max_tries=5, factor=2, jitter=backoff.full_jitter)
    def get_query_result(self, conversation_id: str, message_id: str, attachment_id: str) -> Dict[str, Any]:
        """Retrieve query results"""
        url = f"/api/2.0/genie/spaces/{self.space_id}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result"
        result = self._workspace_client.api_client.do('GET', url)
        data_array = result.get('statement_response', {}).get('result', {}).get('data_array', [])
        return {
            'data_array': data_array,
            'schema': result.get('statement_response', {}).get('manifest', {}).get('schema', {})
        }
    
    @backoff.on_exception(backoff.expo, Exception, max_tries=5, factor=2, jitter=backoff.full_jitter)
    def list_conversation_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """List all messages in a conversation using Genie API"""
        url = f"/api/2.0/genie/spaces/{self.space_id}/conversations/{conversation_id}/messages"
        logger.info(f"📥 Fetching messages from Genie API for conversation: {conversation_id}")
        response = self._workspace_client.api_client.do('GET', url)
        messages = response.get('messages', [])
        logger.info(f"📊 Genie API returned {len(messages)} messages for conversation {conversation_id}")
        return messages

    def wait_for_message_completion(self, conversation_id: str, message_id: str, timeout: int = 300, poll_interval: int = 2) -> Dict[str, Any]:
        """Poll Genie message until completion"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            message = self.get_message(conversation_id, message_id)
            status = message.get("status")
            if status in ["COMPLETED", "ERROR", "FAILED"]:
                return message
            time.sleep(poll_interval)
        raise TimeoutError(f"Message processing timed out after {timeout} seconds")

# ------------------------------------------------------------------------------
# Conversation helpers
# ------------------------------------------------------------------------------
def start_new_conversation(question: str, token_minter: TokenMinter = None, user_info: Optional[Dict[str, Any]] = None) -> Tuple[str, Union[str, pd.DataFrame], Optional[str]]:
    """Start a Genie conversation"""
    client = GenieClient(
        host=DATABRICKS_HOST,
        space_id=SPACE_ID,
        token_minter=token_minter
    )

    try:
        response = client.start_conversation(question)
        conversation_id = response.get("conversation_id")
        message_id = response.get("message_id")
        
        # Log start conversation event using provided user_info
        if user_info:
            try:
                log_start_conversation(
                    user_id=user_info['user_id'],
                    conversation_id=conversation_id,
                    message_id=message_id,
                    user_email=user_info.get('user_email'),
                    user_name=user_info.get('user_name'),
                    question=question[:500]  # Limit question length
                )
            except Exception as log_err:
                logger.warning(f"Failed to log start_conversation event: {log_err}")

        complete_message = client.wait_for_message_completion(conversation_id, message_id)
        result, query_text = process_genie_response(client, conversation_id, message_id, complete_message)
        
        # Log SQL response if query was returned
        if query_text and user_info:
            try:
                log_sql_response(
                    user_id=user_info['user_id'],
                    conversation_id=conversation_id,
                    message_id=message_id,
                    question=question,
                    sql_query=query_text,
                    user_email=user_info.get('user_email'),
                    user_name=user_info.get('user_name')
                )
                logger.info(f"✅ Logged SQL response for message {message_id}")
            except Exception as log_err:
                logger.warning(f"Failed to log SQL response: {log_err}")
        
        return conversation_id, result, query_text

    except Exception as e:
        return None, f"Sorry, an error occurred: {str(e)}", None


def continue_conversation(conversation_id: str, question: str, token_minter: TokenMinter = None, user_info: Optional[Dict[str, Any]] = None) -> Tuple[Union[str, pd.DataFrame], Optional[str]]:
    """Continue an existing Genie conversation"""
    logger.info(f"Continuing conversation {conversation_id} with: {question[:30]}...")
    client = GenieClient(
        host=DATABRICKS_HOST,
        space_id=SPACE_ID,
        token_minter=token_minter
    )
    try:
        response = client.send_message(conversation_id, question)
        message_id = response.get("message_id")
        
        # Log send message event using provided user_info
        if user_info:
            try:
                log_send_message(
                    user_id=user_info['user_id'],
                    conversation_id=conversation_id,
                    message_id=message_id,
                    user_email=user_info.get('user_email'),
                    user_name=user_info.get('user_name'),
                    message=question[:500]  # Limit message length
                )
            except Exception as log_err:
                logger.warning(f"Failed to log send_message event: {log_err}")

        complete_message = client.wait_for_message_completion(conversation_id, message_id)
        result, query_text = process_genie_response(client, conversation_id, message_id, complete_message)
        
        # Log SQL response if query was returned
        if query_text and user_info:
            try:
                log_sql_response(
                    user_id=user_info['user_id'],
                    conversation_id=conversation_id,
                    message_id=message_id,
                    question=question,
                    sql_query=query_text,
                    user_email=user_info.get('user_email'),
                    user_name=user_info.get('user_name')
                )
                logger.info(f"✅ Logged SQL response for message {message_id}")
            except Exception as log_err:
                logger.warning(f"Failed to log SQL response: {log_err}")
        
        return result, query_text

    except Exception as e:
        logger.error(f"Error continuing conversation: {str(e)}")
        return f"Sorry, an error occurred: {str(e)}", None


def process_genie_response(client, conversation_id, message_id, complete_message) -> Tuple[Union[str, pd.DataFrame], Optional[str]]:
    """Interpret Genie API response"""
    attachments = complete_message.get("attachments", [])
    for attachment in attachments:
        attachment_id = attachment.get("attachment_id")
        if "text" in attachment and "content" in attachment["text"]:
            return attachment["text"]["content"], None
        elif "query" in attachment:
            query_text = attachment.get("query", {}).get("query", "")
            query_result = client.get_query_result(conversation_id, message_id, attachment_id)
            data_array = query_result.get('data_array', [])
            schema = query_result.get('schema', {})
            columns = [col.get('name') for col in schema.get('columns', [])]
            if data_array:
                if not columns and len(data_array) > 0:
                    columns = [f"column_{i}" for i in range(len(data_array[0]))]
                df = pd.DataFrame(data_array, columns=columns)
                return df, query_text
    if 'content' in complete_message:
        return complete_message.get('content', ''), None
    return "No response available", None


def genie_query(question: str, conversation_id: str = None, token_minter: TokenMinter = None, user_info: Optional[Dict[str, Any]] = None) -> Union[Tuple[str, Optional[str], Optional[str]], Tuple[pd.DataFrame, str, str]]:
    """Main Genie query entry point"""
    try:
        if conversation_id:
            result, query_text = continue_conversation(conversation_id, question, token_minter, user_info)
            return result, query_text, conversation_id
        else:
            conversation_id, result, query_text = start_new_conversation(question, token_minter, user_info)
            return result, query_text, conversation_id
    except Exception as e:
        logger.error(f"Error in Genie conversation: {str(e)}")