"""One-time re-authorization helper.

Spotify refresh tokens expire 6 months after user authorization (policy
effective for existing apps on 2026-07-20), so this needs to be re-run
roughly every 5-6 months:

    python reauth.py

Requires a .env file with SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, and
SPOTIPY_REDIRECT_URI (values from https://developer.spotify.com/dashboard —
the redirect URI must exactly match one registered on the app).
"""
import os
import sys

from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPES = "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private"

load_dotenv()

missing = [k for k in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "SPOTIPY_REDIRECT_URI") if not os.getenv(k)]
if missing:
    sys.exit(f"Missing {', '.join(missing)} — create a .env file with values from the Spotify developer dashboard.")

# Drop the old cache so the flow mints a brand-new refresh token instead of
# trying (and failing) to refresh the expired one.
if os.path.exists(".cache"):
    os.remove(".cache")

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope=SCOPES,
    open_browser=False,  # no browser inside WSL; prints the URL to open manually
))

user = sp.current_user()
print(f"\nAuthorized as {user['display_name']} ({user['id']}). New token written to .cache.")
print("Now update the GitHub secret so the workflow uses it:\n")
print("    gh secret set SPOTIPY_CACHE < .cache\n")
