import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import random
import sys

load_dotenv()

print("Script starting...", flush=True)
print(f"Cache file exists: {os.path.exists('.cache')}", flush=True)
if os.path.exists('.cache'):
    with open('.cache', 'r') as f:
        content = f.read()
        print(f"Cache content length: {len(content)}", flush=True)
        print(f"Cache starts with: {content[:50]}...", flush=True)

MAIN_PLAYLIST = "June 2025+ Allstars"
FAVORITES_PLAYLIST = "Favorites"
FAVORITE_PLAYLIST = "Favorite"  # 2x weight

SCOPES = "playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private"


def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=SCOPES,
        open_browser=False
    ))


def get_playlist_tracks(sp, name):
    playlists = sp.current_user_playlists(limit=50)
    for playlist in playlists['items']:
        if playlist['name'].strip().lower() == name.strip().lower():
            tracks = []
            results = sp.playlist_tracks(playlist['id'])
            tracks.extend(results['items'])
            while results['next']:
                results = sp.next(results)
                tracks.extend(results['items'])
            return playlist['id'], tracks
    return None, None


def get_track_ids(tracks):
    if not tracks:
        return set()
    return {item['track']['id'] for item in tracks if item['track']}


def weighted_shuffle(all_tracks, favorite_ids, double_weight_ids):
    pool = []
    for item in all_tracks:
        track = item['track']
        if not track:
            continue
        is_double = track['id'] in double_weight_ids
        is_fav = track['id'] in favorite_ids or is_double
        pool.append({
            'id': track['id'],
            'uri': track['uri'],
            'name': track['name'],
            'is_fav': is_fav,
            'is_double': is_double,
            'weight': 1.0
        })

    result = []
    last_id = None

    while pool:
        total = sum(t['weight'] for t in pool)
        r = random.random() * total
        cumulative = 0
        idx = 0
        for i, t in enumerate(pool):
            cumulative += t['weight']
            if r <= cumulative:
                idx = i
                break

        selected = pool.pop(idx)

        if selected['id'] == last_id and pool:
            pool.append(selected)
            continue

        result.append(selected)
        last_id = selected['id']

        if selected['is_fav']:
            pool.append({
                'id': selected['id'],
                'uri': selected['uri'],
                'name': selected['name'],
                'is_fav': True,
                'is_double': selected['is_double'],
                'weight': 2.0 if selected['is_double'] else 1.0
            })

    return result


def reorder_playlist(sp, playlist_id, uris):
    sp.playlist_replace_items(playlist_id, [])
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist_id, uris[i:i+100])


def main():
    print("Creating Spotify client...", flush=True)
    sp = get_spotify_client()
    print("Client created, fetching user...", flush=True)
    user = sp.current_user()
    print(f"Authenticated as: {user['display_name']}", flush=True)

    # Debug: show all playlist names
    playlists = sp.current_user_playlists(limit=50)
    print("\nYour playlists:")
    for p in playlists['items']:
        print(f"  - '{p['name']}'")

    main_id, main_tracks = get_playlist_tracks(sp, MAIN_PLAYLIST)
    if not main_id:
        print(f"\nCould not find playlist: '{MAIN_PLAYLIST}'")
        return
    print(f"Main playlist: {len(main_tracks)} tracks")

    _, fav_tracks = get_playlist_tracks(sp, FAVORITES_PLAYLIST)
    if not fav_tracks:
        print(f"Could not find playlist: {FAVORITES_PLAYLIST}")
        return
    favorite_ids = get_track_ids(fav_tracks)
    print(f"Favorites: {len(favorite_ids)} tracks")

    _, double_tracks = get_playlist_tracks(sp, FAVORITE_PLAYLIST)
    double_weight_ids = get_track_ids(double_tracks)
    if double_weight_ids:
        print(f"Favorite (2x): {len(double_weight_ids)} tracks")

    shuffled = weighted_shuffle(main_tracks, favorite_ids, double_weight_ids)

    print(f"\nShuffled order: {len(shuffled)} tracks")
    for i, t in enumerate(shuffled[:15], 1):
        marker = "(2x)" if t['is_double'] else "(1x)" if t['is_fav'] else ""
        print(f"  {i}. {t['name']} {marker}")

    reorder_playlist(sp, main_id, [t['uri'] for t in shuffled])
    print(f"\nDone. Playlist reordered.")


if __name__ == "__main__":
    main()
