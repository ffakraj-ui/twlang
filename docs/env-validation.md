# Environment variable validation

Declare required env vars in tw.config:

    env:
      required: "FIREBASE_PROJECT_ID, DATABASE_URL, API_TOKEN"

tw dev will warn at startup if any are missing from .env, .env.development, .env.local, or the shell environment. This is a warning, not a hard failure -- the server still starts.

The check runs once at startup, not on every hot-reload.
