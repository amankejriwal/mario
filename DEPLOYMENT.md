# Deploying Mario as a Databricks App

This guide explains how to deploy Mario as a Databricks App with automatic user authentication.

## How Authentication Works

When deployed as a Databricks App with `require_user_authentication: true`:

1. **User Access**: Users navigate to your app's Databricks URL
2. **Auto-Login**: If not logged in, Databricks shows the login screen
3. **Authenticated Session**: Once logged in, their credentials automatically flow to the app
4. **User-Specific API Calls**: All Genie API calls use the authenticated user's identity
5. **Feedback Attribution**: Feedback is correctly attributed to the user who provided it

## Deployment Steps

### 1. Update app.yaml Configuration

Make sure your `app.yaml` has the correct Space ID:

```yaml
env:
- name: "SPACE_ID"
  value: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # Replace with your actual Genie Space ID
```

### 2. Deploy to Databricks

Using the Databricks CLI:

```bash
# Navigate to your project directory
cd /Users/amankejriwal/Documents/GitHub/genie/genie_space/genie_space

# Deploy the app
databricks apps deploy <app-name>
```

Or using the Databricks UI:
- Go to your Databricks workspace
- Navigate to Apps
- Click "Create App"
- Upload your code or connect to your Git repository
- Databricks will use the `app.yaml` configuration

### 3. Access Your App

Once deployed, you'll get a URL like:
```
https://<workspace>.cloud.databricks.com/apps/<app-name>
```

Share this URL with your users. They'll be prompted to log in if not already authenticated.

## How It Works

### Authentication Flow

```
User → Databricks Login → Authenticated Session → Your App
                                                      ↓
                                          WorkspaceClient() 
                                          (auto-configured with user's credentials)
                                                      ↓
                                          Genie API Calls
                                          (using user's token)
```

### Code Structure

1. **TokenMinter** (`token_minter.py`):
   - Uses `WorkspaceClient()` which auto-configures with user credentials
   - No manual token management needed
   - Each user gets their own token automatically

2. **Genie API Calls** (`genie_room.py`):
   - All calls pass through user-specific `TokenMinter`
   - Conversations and feedback tied to actual user

3. **App Callbacks** (`app.py`):
   - Each callback gets a fresh `TokenMinter` for the current user
   - User identity preserved throughout the session

## Local Development

For local development without deploying:

1. Create a `.env` file with your personal access token:
   ```bash
   DATABRICKS_TOKEN=your-personal-access-token
   DATABRICKS_HOST=your-workspace.cloud.databricks.com
   SPACE_ID=your-genie-space-id
   ```

2. Run the app:
   ```bash
   python app.py
   ```

**Note**: In local mode, all API calls use YOUR token (the developer). For proper user authentication, deploy as a Databricks App.

## Troubleshooting

### "No authentication token available" Error

**Cause**: App is not deployed as a Databricks App, or `require_user_authentication` is not enabled.

**Solution**: 
1. Ensure `app.yaml` has `require_user_authentication: true`
2. Deploy using `databricks apps deploy`
3. For local development, add `DATABRICKS_TOKEN` to `.env`

### Feedback Not Attributed to User

**Cause**: Using a shared service account token instead of user-specific tokens.

**Solution**: This is now fixed! Each user's token is automatically used when the app is deployed as a Databricks App.

## Security Best Practices

✅ **DO**:
- Deploy as a Databricks App with `require_user_authentication: true`
- Use user-specific authentication for all API calls
- Let Databricks SDK handle authentication automatically

❌ **DON'T**:
- Share service account tokens across users
- Hardcode tokens in code
- Disable user authentication in production

## Support

For issues or questions, refer to:
- [Databricks Apps Documentation](https://docs.databricks.com/dev-tools/databricks-apps/index.html)
- [Databricks SDK Python Documentation](https://databricks-sdk-py.readthedocs.io/)
