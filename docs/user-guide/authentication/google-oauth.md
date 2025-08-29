# Google OAuth Integration

This guide explains how to integrate Google OAuth authentication with your FastAPI backend and Next.js frontend.

## Backend Setup

### 1. Google Cloud Console Setup

First, you need to set up OAuth credentials in Google Cloud Console:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Set application type to "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:8000/api/v1/auth/google/callback` (development)
   - `https://yourdomain.com/api/v1/auth/google/callback` (production)

### 2. Environment Configuration

Add your Google OAuth credentials to your `.env` file:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
FRONTEND_URL=http://localhost:3000
```

### 3. Available Endpoints

The backend provides these OAuth endpoints:

- `GET /api/v1/auth/google/login` - Initiates Google OAuth flow
- `GET /api/v1/auth/google/callback` - Handles OAuth callback
- `GET /api/v1/auth/google/user` - Gets user info (for testing)

## Security Considerations

1. **HTTPS in Production**: Always use HTTPS in production for OAuth callbacks
2. **Token Storage**: Consider using secure HTTP-only cookies instead of localStorage for production
3. **CORS Configuration**: Ensure your backend CORS settings allow your frontend domain
4. **Environment Variables**: Never expose client secrets in frontend code
5. **Token Refresh**: Implement token refresh logic for better user experience

## Troubleshooting

### Common Issues

1. **Redirect URI Mismatch**: Ensure the redirect URI in Google Console matches exactly
2. **CORS Errors**: Check your backend CORS configuration
3. **Token Not Found**: Verify the callback URL parameters are being passed correctly
4. **User Creation Fails**: Check if email/username conflicts exist in your database

### Testing OAuth Flow

1. Start your backend server: `docker compose up`
2. Start your Next.js frontend: `npm run dev`
3. Navigate to `/login` and click "Continue with Google"
4. Complete the Google OAuth flow
5. Verify you're redirected back with a valid token

The OAuth integration is now complete! Users can sign in with Google and the backend will automatically create user accounts or authenticate existing ones.