# Spotify Weighted Shuffle

A personal project to create a weighted shuffle system for Spotify playlists, where certain "favorite" tracks appear more frequently than others during playback.

## Background

Spotify's native shuffle treats all tracks equally. For playlists where I have a handful of songs I want to hear more often than the rest, there's no built-in way to weight the shuffle in their favor. I wanted a system where my top 5-7 tracks from a playlist would naturally appear multiple times throughout a listening session, while the remaining 30+ tracks would each play exactly once.

## The Problem

The initial approach seemed straightforward: assign each song a weight and sample from that distribution. But this introduced edge cases around repetition. What if a "normal" track gets randomly selected twice before the playlist cycles? I'd need additional attributes to track repeatability, which felt overly complicated for what should be a simple idea.

## The Solution

I landed on a cleaner model inspired by sampling theory:

- All tracks start in a pool with equal weight
- When a track is selected, it's removed from the pool
- Normal tracks stay removed (sampled without replacement)
- Favorite tracks are added back to the pool (sampled with replacement)
- The process continues until a target length is reached

This approach naturally produces the behavior I wanted: favorites recur throughout the playlist, normal tracks play once, and no song repeats back-to-back.

## How It Works

Since Spotify's shuffle algorithm can't be modified directly, the script takes a different approach. It generates a weighted shuffle order and physically reorders the playlist via the Spotify API. The playlist is then played in order (with Spotify's shuffle turned off), but the order itself is the weighted shuffle.

The script reads from two additional playlists to determine favorites:
- **Favorites** (1x weight): tracks that get re-added to the pool after playing
- **Favorite** (2x weight): a single track I want even more frequently

A GitHub Actions workflow runs every 6 hours to reshuffle the playlist automatically, so each listening session has a fresh order without any manual intervention.

## Technical Notes

Built with Python using the Spotipy library for Spotify API access. The automation runs on GitHub Actions using OAuth tokens stored as repository secrets. The weighted sampling algorithm handles edge cases like preventing consecutive plays of the same track and ensuring the pool eventually empties to a target length.

## Important Edits

After running it a few times, I realized that changing the *original* playlist to the shuffled version w/ duplicates (simulating "weights") was annoying because if I ever wanted to add new songs to the playlist, I would effectively be adding new songs to the *weighted* playlist. To combat this issue, I modified it such that it now takes the original playlist, without duplicates, and uses that to create a new, *weighted* playlist based on all the songs from the original playlist. Now, I can add songs to the original playlist, favorites playlist, and favorite playlist and the reshuffle (whether scheduled or manual) will automatically take those into effect in editing the new playlist, without polluting the original. 

