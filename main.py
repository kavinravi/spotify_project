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

SOURCE_PLAYLIST = "June 2025+ Allstars"
OUTPUT_PLAYLIST = "June 2025+ Allstars (Weighted)"
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


MIN_REPEAT_GAP = 3  # min number of songs before a song can repeat


def redistribute_favorites(tracks):
    """
    Post-process to spread favorite appearances evenly across the playlist.
    Instead of clustering at the end, favorites are distributed throughout.
    """
    total_len = len(tracks)
    
    # Separate non-favorites and collect favorite appearances by ID
    non_favorites = []
    favorite_appearances = {}  # id -> list of track dicts
    
    for t in tracks:
        if t['is_fav']:
            if t['id'] not in favorite_appearances:
                favorite_appearances[t['id']] = []
            favorite_appearances[t['id']].append(t)
        else:
            non_favorites.append(t)
    
    # Calculate evenly-spaced positions for each favorite
    reserved_positions = {}  # position -> track
    
    for fav_id, appearances in favorite_appearances.items():
        count = len(appearances)
        # Spread evenly with some randomness to avoid predictable patterns
        spacing = total_len / count
        for i, track in enumerate(appearances):
            # Ideal position with slight random offset
            ideal_pos = int(spacing * i + spacing / 2)
            ideal_pos = max(0, min(total_len - 1, ideal_pos))
            # Find nearest free position
            offset = 0
            while True:
                for try_pos in [ideal_pos + offset, ideal_pos - offset]:
                    if 0 <= try_pos < total_len and try_pos not in reserved_positions:
                        reserved_positions[try_pos] = track
                        break
                else:
                    offset += 1
                    continue
                break
    
    # Build final playlist: favorites at reserved positions, non-favorites fill gaps
    result = [None] * total_len
    for pos, track in reserved_positions.items():
        result[pos] = track
    
    non_fav_iter = iter(non_favorites)
    for i in range(total_len):
        if result[i] is None:
            result[i] = next(non_fav_iter, None)
    
    # Remove any None entries (shouldn't happen but safety)
    result = [t for t in result if t is not None]
    
    # Final pass: ensure MIN_REPEAT_GAP is respected
    result = enforce_min_gap(result)
    
    return result


def enforce_min_gap(tracks):
    """Swap tracks to ensure no song repeats within MIN_REPEAT_GAP positions."""
    for i in range(len(tracks)):
        track_id = tracks[i]['id']
        # Check if this track appeared in the last MIN_REPEAT_GAP positions
        for j in range(max(0, i - MIN_REPEAT_GAP), i):
            if tracks[j]['id'] == track_id:
                # Find a track to swap with (look ahead for a non-conflicting track)
                for k in range(i + 1, len(tracks)):
                    # Check if swapping would be safe
                    swap_id = tracks[k]['id']
                    # Make sure the swap target isn't also conflicting at position i
                    conflict = False
                    for m in range(max(0, i - MIN_REPEAT_GAP), i):
                        if tracks[m]['id'] == swap_id:
                            conflict = True
                            break
                    if not conflict:
                        tracks[i], tracks[k] = tracks[k], tracks[i]
                        break
                break
    return tracks


def weighted_shuffle(all_tracks, favorite_ids, double_weight_ids):
    pool = []
    num_favorites = 0
    for item in all_tracks:
        track = item['track']
        if not track:
            continue
        is_double = track['id'] in double_weight_ids
        is_fav = track['id'] in favorite_ids or is_double
        if is_fav:
            num_favorites += 1
        pool.append({
            'id': track['id'],
            'uri': track['uri'],
            'name': track['name'],
            'is_fav': is_fav,
            'is_double': is_double,
            'weight': 1.0
        })

    # Target length: all tracks + extra appearances for favorites
    num_unique = len(pool)
    target_length = num_unique + num_favorites * 2
    print(f"Shuffle: {num_unique} unique tracks, {num_favorites} favorites, target {target_length}", flush=True)

    result = []
    recent_ids = []  # Track last N song IDs to enforce minimum gap

    while pool and len(result) < target_length:
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

        # Check if this song was played too recently
        if selected['id'] in recent_ids and pool:
            pool.append(selected)
            continue

        result.append(selected)
        recent_ids.append(selected['id'])
        if len(recent_ids) > MIN_REPEAT_GAP:
            recent_ids.pop(0)

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


def get_or_create_playlist(sp, user_id, name):
    playlists = sp.current_user_playlists(limit=50)
    for playlist in playlists['items']:
        if playlist['name'].strip().lower() == name.strip().lower():
            return playlist['id']
    # Create if not found
    new_playlist = sp.user_playlist_create(user_id, name, public=False)
    return new_playlist['id']


def update_playlist(sp, playlist_id, uris):
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

    # Read from source playlist
    _, source_tracks = get_playlist_tracks(sp, SOURCE_PLAYLIST)
    if not source_tracks:
        print(f"\nCould not find playlist: '{SOURCE_PLAYLIST}'")
        return
    print(f"Source playlist: {len(source_tracks)} tracks")

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

    shuffled = weighted_shuffle(source_tracks, favorite_ids, double_weight_ids)
    shuffled = redistribute_favorites(shuffled)

    print(f"\nShuffled order: {len(shuffled)} tracks")
    for i, t in enumerate(shuffled[:15], 1):
        marker = "(2x)" if t['is_double'] else "(1x)" if t['is_fav'] else ""
        print(f"  {i}. {t['name']} {marker}")

    # Write to output playlist (create if needed)
    output_id = get_or_create_playlist(sp, user['id'], OUTPUT_PLAYLIST)
    update_playlist(sp, output_id, [t['uri'] for t in shuffled])
    print(f"\nDone. Output playlist '{OUTPUT_PLAYLIST}' updated.")


if __name__ == "__main__":
    main()
