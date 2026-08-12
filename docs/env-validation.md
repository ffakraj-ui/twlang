# Environment variable validation

Declare required env vars in tw.config:

    env:
      required: "FIREBASE_PROJECT_ID, DATABASE_URL, API_TOKEN"

tw dev will warn at startup if any are missing from .env, .env.development, .env.local, or the shell environment. This is a warning, not a hard failure -- the server still starts.

The check runs once at startup, not on every hot-reload.

## Types

You can also validate the shape of a value, not just its presence:

    env:
      required: "API_TOKEN"
      types: "PORT:number, API_URL:url, DEBUG_MODE:boolean"

Supported types: number, url (must start with http:// or https://), boolean (true/false/1/0/yes/no). A var listed in types but not in required is only checked when it is actually set -- an absent optional var is not an error.

## Types

You can also validate the shape of a value, not just its presence:

    env:
      required: "API_TOKEN"
      types: "PORT:number, API_URL:url, DEBUG_MODE:boolean"

Supported types: number, url (must start with http:// or https://), boolean (true/false/1/0/yes/no). A var listed in types but not in required is only checked when it is actually set -- an absent optional var is not an error.
