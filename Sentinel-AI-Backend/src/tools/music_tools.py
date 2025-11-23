# src/tools/music_tools.py

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from langchain_core.tools import tool
from dotenv import load_dotenv
import webbrowser
import urllib.parse
import requests
from bs4 import BeautifulSoup
import re

# Import user-specific Spotify authentication
from src.utils.spotify_user_auth import get_user_spotify_client

load_dotenv() # Load environment variables

# --- Spotify API Setup ---
# NOTE: Spotify authentication is now USER-SPECIFIC!
# Each tool will fetch the appropriate Spotify client for the current user
# using get_user_spotify_client() which reads from user_context.json and MongoDB

def _get_spotify_client():
    """
    Get user-specific Spotify client.
    Returns (sp_client, error_message) tuple.
    """
    sp = get_user_spotify_client()
    if not sp:
        return None, ("Spotify not connected. Please connect your Spotify account in the dashboard. "
                      "Go to Dashboard -> Spotify -> Connect to authorize your account.")
    return sp, None

# --- Tool Definitions ---

@tool
def search_and_play_song(song_name: str, artist_name: str = None) -> str:
    """
    Searches for a song on Spotify and plays it on the user's active device.
    You can optionally provide an artist's name to improve the search accuracy.
    """
    sp, error = _get_spotify_client()
    if not sp:
        return error

    try:
        # Check for active devices
        devices = sp.devices()
        if not devices or not devices['devices']:
            return "No active Spotify device found. Please open Spotify on one of your devices and start playing something."
        
        active_device_id = None
        for device in devices['devices']:
            if device['is_active']:
                active_device_id = device['id']
                break
        
        if not active_device_id:
            # If no device is active, use the first available one.
            active_device_id = devices['devices'][0]['id']


        # Construct the search query
        query = f"track:{song_name}"
        if artist_name:
            query += f" artist:{artist_name}"

        # Search for the track
        results = sp.search(q=query, type='track', limit=1)
        tracks = results['tracks']['items']

        if not tracks:
            return f"Could not find the song '{song_name}'."

        # Get the track URI and play it
        track_uri = tracks[0]['uri']
        sp.start_playback(device_id=active_device_id, uris=[track_uri])

        return f"Now playing '{tracks[0]['name']}' by {tracks[0]['artists'][0]['name']}."

    except Exception as e:
        return f"An error occurred: {e}. I might need you to be more specific or check if a song is already playing on Spotify."

# Fix Required
@tool
def next_song() -> str:
    """
    Skips to the next song in the current Spotify playlist or queue.
    """
    sp, error = _get_spotify_client()
    if not sp:
        return error

    try:
        # Check for active devices
        devices = sp.devices()
        if not devices or not devices['devices']:
            return "No active Spotify device found. Please open Spotify on one of your devices."
        
        # Skip to next track
        sp.next_track()
        
        # Get current playing track info
        current_track = sp.current_playback()
        if current_track and current_track['item']:
            track_name = current_track['item']['name']
            artist_name = current_track['item']['artists'][0]['name']
            return f"Skipped to next song: '{track_name}' by {artist_name}."
        else:
            return "Skipped to next song."

    except Exception as e:
        return f"An error occurred while skipping to next song: {e}"

# Fix Required
@tool
def previous_song() -> str:
    """
    Goes back to the previous song in the current Spotify playlist or queue.
    """
    sp, error = _get_spotify_client()
    if not sp:
        return error

    try:
        # Check for active devices
        devices = sp.devices()
        if not devices or not devices['devices']:
            return "No active Spotify device found. Please open Spotify on one of your devices."
        
        # Skip to previous track
        sp.previous_track()
        
        # Get current playing track info
        current_track = sp.current_playback()
        if current_track and current_track['item']:
            track_name = current_track['item']['name']
            artist_name = current_track['item']['artists'][0]['name']
            return f"Went back to previous song: '{track_name}' by {artist_name}."
        else:
            return "Went back to previous song."

    except Exception as e:
        return f"An error occurred while going to previous song: {e}"


@tool
def pause_music() -> str:
    """
    Pauses the currently playing music on Spotify.
    """
    sp, error = _get_spotify_client()
    if not sp:
        return error

    try:
        # Check if something is currently playing
        current_playback = sp.current_playback()
        if not current_playback or not current_playback['is_playing']:
            return "No music is currently playing on Spotify."
        
        # Pause playback
        sp.pause_playback()
        
        track_name = current_playback['item']['name']
        artist_name = current_playback['item']['artists'][0]['name']
        return f"Paused: '{track_name}' by {artist_name}."

    except Exception as e:
        return f"An error occurred while pausing music: {e}"


@tool
def resume_music() -> str:
    """
    Resumes the paused music on Spotify.
    """
    sp, error = _get_spotify_client()
    if not sp:
        return error

    try:
        # Check current playback state
        current_playback = sp.current_playback()
        if current_playback and current_playback['is_playing']:
            track_name = current_playback['item']['name']
            artist_name = current_playback['item']['artists'][0]['name']
            return f"Music is already playing: '{track_name}' by {artist_name}."
        
        # Resume playback
        sp.start_playback()
        
        # Get track info after resuming
        current_playback = sp.current_playback()
        if current_playback and current_playback['item']:
            track_name = current_playback['item']['name']
            artist_name = current_playback['item']['artists'][0]['name']
            return f"Resumed: '{track_name}' by {artist_name}."
        else:
            return "Music resumed."

    except Exception as e:
        return f"An error occurred while resuming music: {e}"

# Fix Required
@tool
def set_volume(volume_percent: int) -> str:
    """
    Sets the volume of the Spotify playback.

    Args:
        volume_percent: Volume level from 0 to 100
    """
    sp, error = _get_spotify_client()
    if not sp:
        return error

    try:
        # Validate volume range
        if volume_percent < 0 or volume_percent > 100:
            return "Volume must be between 0 and 100."
        
        # Check for active devices
        devices = sp.devices()
        if not devices or not devices['devices']:
            return "No active Spotify device found. Please open Spotify on one of your devices."
        
        # Get active device or use first available
        active_device_id = None
        for device in devices['devices']:
            if device['is_active']:
                active_device_id = device['id']
                break
        
        if not active_device_id:
            active_device_id = devices['devices'][0]['id']
        
        # Set volume on the specific device
        sp.volume(volume_percent, device_id=active_device_id)
        return f"Volume set to {volume_percent}%."

    except Exception as e:
        # More specific error handling
        error_msg = str(e)
        if "Premium required" in error_msg:
            return "Volume control requires Spotify Premium subscription."
        elif "Device not found" in error_msg:
            return "The selected device is no longer available. Please check your Spotify devices."
        else:
            return f"An error occurred while setting volume: {e}"


@tool
def get_current_song() -> str:
    """
    Gets information about the currently playing song on Spotify.
    """
    sp, error = _get_spotify_client()
    if not sp:
        return error

    try:
        current_playback = sp.current_playback()
        
        if not current_playback:
            return "No music information available. Make sure Spotify is open and you have an active session."
        
        if not current_playback['is_playing']:
            if current_playback['item']:
                track_name = current_playback['item']['name']
                artist_name = current_playback['item']['artists'][0]['name']
                return f"Music is paused: '{track_name}' by {artist_name}."
            else:
                return "Music is paused."
        
        # Get track information
        track = current_playback['item']
        track_name = track['name']
        artist_name = track['artists'][0]['name']
        album_name = track['album']['name']
        
        # Get progress information
        progress_ms = current_playback['progress_ms']
        duration_ms = track['duration_ms']
        progress_min = progress_ms // 60000
        progress_sec = (progress_ms % 60000) // 1000
        duration_min = duration_ms // 60000
        duration_sec = (duration_ms % 60000) // 1000
        
        return f"Currently playing: '{track_name}' by {artist_name} from the album '{album_name}'. Progress: {progress_min}:{progress_sec:02d} / {duration_min}:{duration_sec:02d}"

    except Exception as e:
        return f"An error occurred while getting current song info: {e}"


# --- YouTube Music Tools ---

@tool
def play_on_youtube_music(song_name: str, artist_name: str = None) -> str:
    """
    [DEPRECATED - Use playwright_play_youtube_music for auto-play instead]
    Searches for a song on YouTube Music and opens search results.
    DOES NOT AUTO-PLAY - user must manually click the song.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
    """
    try:
        # Construct search query
        if artist_name:
            search_query = f"{song_name} {artist_name}"
        else:
            search_query = song_name
        
        # URL encode the search query
        encoded_query = urllib.parse.quote_plus(search_query)
        
        # YouTube Music search URL
        youtube_music_url = f"https://music.youtube.com/search?q={encoded_query}"
        
        # Open in browser
        webbrowser.open(youtube_music_url)
        
        if artist_name:
            return f"🎵 Opened YouTube Music search for '{song_name}' by {artist_name}. The first result should be your song - click the play button to start listening!"
        else:
            return f"🎵 Opened YouTube Music search for '{song_name}'. The first result should be your song - click the play button to start listening!"
        
    except Exception as e:
        return f"Error opening YouTube Music: {e}"


@tool
def play_on_youtube(song_name: str, artist_name: str = None) -> str:
    """
    [DEPRECATED - Use playwright_play_youtube for auto-play instead]
    Searches for a song on regular YouTube and opens search results.
    DOES NOT AUTO-PLAY - user must manually click the video.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
    """
    try:
        # Construct search query
        if artist_name:
            search_query = f"{song_name} {artist_name}"
        else:
            search_query = song_name
        
        # URL encode the search query
        encoded_query = urllib.parse.quote_plus(search_query)
        
        # YouTube search URL that often auto-plays first result
        youtube_url = f"https://www.youtube.com/results?search_query={encoded_query}"
        
        # Open in browser
        webbrowser.open(youtube_url)
        
        if artist_name:
            return f"� Opened YouTube search for '{song_name}' by {artist_name}. Click on the first video to play it instantly!"
        else:
            return f"🎥 Opened YouTube search for '{song_name}'. Click on the first video to play it instantly!"
        
    except Exception as e:
        return f"Error opening YouTube: {e}"


@tool
def play_music_smart(song_name: str, artist_name: str = None, platform: str = "auto") -> str:
    """
    Smart music player that tries multiple platforms to play a song.
    First tries Spotify, then falls back to YouTube Music or YouTube.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
        platform: "spotify", "youtube_music", "youtube", or "auto" (tries all)
    """
    try:
        # If platform is specified, use that directly
        if platform == "spotify":
            return search_and_play_song(song_name, artist_name)
        elif platform == "youtube_music":
            return play_on_youtube_music(song_name, artist_name)
        elif platform == "youtube":
            return play_on_youtube(song_name, artist_name)

        # Auto mode: try Spotify first, then YouTube options
        sp, _ = _get_spotify_client()
        if sp:  # Spotify is available for this user
            try:
                result = search_and_play_song(song_name, artist_name)
                if "error" not in result.lower() and "failed" not in result.lower() and "not connected" not in result.lower():
                    return result + " (via Spotify)"
            except:
                pass

        # If Spotify failed or unavailable, try auto-play YouTube
        return auto_play_youtube_song(song_name, artist_name)

    except Exception as e:
        return f"Error in smart music player: {e}"


@tool
def auto_play_youtube_song(song_name: str, artist_name: str = None) -> str:
    """
    Plays a song on REGULAR YOUTUBE (not YouTube Music) in your logged-in browser.
    Opens YouTube in your existing browser where you're already signed in.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
    """
    try:
        # Construct search query
        if artist_name:
            search_query = f"{song_name} {artist_name} official"
        else:
            search_query = f"{song_name} official"

        # URL encode the search query
        encoded_query = urllib.parse.quote_plus(search_query)

        # YouTube search URL to scrape results
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # Get search results
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()

        # Find the first video URL in the results
        # Look for video IDs in the HTML
        video_id_pattern = r'"videoId":"([^"]{11})"'
        matches = re.findall(video_id_pattern, response.text)

        if matches:
            # Get the first video ID
            first_video_id = matches[0]

            # Construct direct YouTube video URL with autoplay
            video_url = f"https://www.youtube.com/watch?v={first_video_id}&autoplay=1"

            # Open in EXISTING default browser (where user is logged in)
            webbrowser.open(video_url)

            if artist_name:
                return f"🎵 Found and auto-playing '{song_name}' by {artist_name} on YouTube in your logged-in browser!"
            else:
                return f"🎵 Found and auto-playing '{song_name}' on YouTube in your logged-in browser!"
        else:
            # Fallback to regular search if no video found
            youtube_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            webbrowser.open(youtube_url)

            return f"🎵 Opened YouTube search for '{search_query}'. Click on the first video to play it!"

    except Exception as e:
        # Fallback to regular search if scraping fails
        try:
            encoded_query = urllib.parse.quote_plus(f"{song_name} {artist_name}" if artist_name else song_name)
            youtube_url = f"https://www.youtube.com/results?search_query={encoded_query}"
            webbrowser.open(youtube_url)

            return f"🎵 Opened YouTube search for your song. Click on the first result to play it! (Auto-detection failed: {e})"
        except:
            return f"Error opening YouTube: {e}"


@tool
def auto_play_youtube_music_song(song_name: str, artist_name: str = None) -> str:
    """
    Plays a song on YOUTUBE MUSIC in your logged-in browser with AUTO-PLAY.
    Opens YouTube Music in your existing browser where you're already signed in.
    This is the RECOMMENDED tool for YouTube Music - uses your existing logged-in browser!

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
    """
    try:
        # Construct search query
        if artist_name:
            search_query = f"{song_name} {artist_name}"
        else:
            search_query = song_name

        # Strategy: Search on regular YouTube first (better scraping), then convert to YouTube Music link
        encoded_query = urllib.parse.quote_plus(search_query)
        youtube_search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        try:
            # Get video ID from YouTube search
            response = requests.get(youtube_search_url, headers=headers, timeout=10)
            response.raise_for_status()

            # Look for video IDs in the HTML (11-character YouTube IDs)
            video_id_pattern = r'"videoId":"([a-zA-Z0-9_-]{11})"'
            matches = re.findall(video_id_pattern, response.text)

            if matches:
                # Get the first video ID
                first_video_id = matches[0]

                # Construct direct YouTube Music video URL (not search URL!)
                video_url = f"https://music.youtube.com/watch?v={first_video_id}"

                # Open in EXISTING default browser (where user is logged in)
                webbrowser.open(video_url)

                if artist_name:
                    return f"🎵 Now playing '{song_name}' by {artist_name} on YouTube Music in your logged-in browser!"
                else:
                    return f"🎵 Now playing '{song_name}' on YouTube Music in your logged-in browser!"
            else:
                # If no video ID found, try alternative pattern
                video_id_pattern_alt = r'/watch\?v=([a-zA-Z0-9_-]{11})'
                matches_alt = re.findall(video_id_pattern_alt, response.text)

                if matches_alt:
                    first_video_id = matches_alt[0]
                    video_url = f"https://music.youtube.com/watch?v={first_video_id}"
                    webbrowser.open(video_url)

                    if artist_name:
                        return f"🎵 Now playing '{song_name}' by {artist_name} on YouTube Music in your logged-in browser!"
                    else:
                        return f"🎵 Now playing '{song_name}' on YouTube Music in your logged-in browser!"

        except Exception as scrape_error:
            print(f"Scraping failed: {scrape_error}")

        # Fallback: If scraping fails, try YouTube Music direct search
        # This will open the search page, but at least it's on YouTube Music
        yt_music_search = f"https://music.youtube.com/search?q={encoded_query}"
        webbrowser.open(yt_music_search)

        if artist_name:
            return f"🎵 Opened YouTube Music search for '{song_name}' by {artist_name} in your logged-in browser. Click the first result to play!"
        else:
            return f"🎵 Opened YouTube Music search for '{song_name}' in your logged-in browser. Click the first result to play!"

    except Exception as e:
        return f"Error opening YouTube Music: {e}"


@tool
def play_youtube_music_direct(song_name: str, artist_name: str = None) -> str:
    """
    Attempts to find and play a song directly on YouTube Music with better auto-play.
    Uses a more direct approach than just search pages.
    
    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
    """
    try:
        # Construct search query
        if artist_name:
            search_query = f"{song_name} {artist_name}"
        else:
            search_query = song_name
        
        # First try auto-play YouTube (often works better)
        youtube_result = auto_play_youtube_song(song_name, artist_name)
        
        # Also open YouTube Music as a backup
        encoded_query = urllib.parse.quote_plus(search_query)
        youtube_music_url = f"https://music.youtube.com/search?q={encoded_query}"
        
        # Small delay to prevent opening both at exactly the same time
        import time
        time.sleep(1)
        
        # Open YouTube Music in a new tab
        webbrowser.open_new_tab(youtube_music_url)
        
        return f"{youtube_result}\n\n🎵 Also opened YouTube Music as backup - if YouTube doesn't auto-play, switch to the YouTube Music tab and click the first song!"
        
    except Exception as e:
        return f"Error in direct music playback: {e}"


@tool
def open_youtube_music() -> str:
    """
    Opens YouTube Music home page in the browser.
    """
    try:
        webbrowser.open("https://music.youtube.com")
        return "🎵 Opened YouTube Music in your browser. You can now browse and play music."
        
    except Exception as e:
        return f"Error opening YouTube Music: {e}"


@tool
def search_youtube_music(query: str) -> str:
    """
    Opens YouTube Music with a general search query.
    Useful for searching albums, playlists, or artists.
    
    Args:
        query: Search term (can be song, artist, album, or playlist)
    """
    try:
        # URL encode the search query
        encoded_query = urllib.parse.quote_plus(query)
        
        # YouTube Music search URL
        youtube_music_url = f"https://music.youtube.com/search?q={encoded_query}"
        
        # Open in browser
        webbrowser.open(youtube_music_url)
        
        return f"🎵 Opened YouTube Music search for '{query}' in your browser. Browse the results to find what you're looking for."
        
    except Exception as e:
        return f"Error searching YouTube Music: {e}"


@tool
def play_youtube_music_playlist(playlist_name: str) -> str:
    """
    Searches for a playlist on YouTube Music and opens it in the browser.
    
    Args:
        playlist_name: Name of the playlist to search for
    """
    try:
        # Add "playlist" to the search to improve results
        search_query = f"{playlist_name} playlist"
        
        # URL encode the search query
        encoded_query = urllib.parse.quote_plus(search_query)
        
        # YouTube Music search URL with playlist filter
        youtube_music_url = f"https://music.youtube.com/search?q={encoded_query}"
        
        # Open in browser
        webbrowser.open(youtube_music_url)
        
        return f"🎵 Opened YouTube Music search for '{playlist_name}' playlist in your browser. Click on the desired playlist to play it."
        
    except Exception as e:
        return f"Error opening YouTube Music playlist: {e}"


@tool
def open_youtube_music_library() -> str:
    """
    Opens the user's YouTube Music library page in the browser.
    Shows liked songs, playlists, and recently played music.
    """
    try:
        webbrowser.open("https://music.youtube.com/library")
        return "🎵 Opened your YouTube Music library in your browser. Here you can access your liked songs, playlists, and recently played music."
        
    except Exception as e:
        return f"Error opening YouTube Music library: {e}"


@tool
def create_youtube_music_station(artist_or_song: str) -> str:
    """
    Creates a radio station on YouTube Music based on an artist or song.
    
    Args:
        artist_or_song: Artist name or song to base the radio station on
    """
    try:
        # Search for the artist/song and let user create station from results
        encoded_query = urllib.parse.quote_plus(artist_or_song)
        youtube_music_url = f"https://music.youtube.com/search?q={encoded_query}"
        
        webbrowser.open(youtube_music_url)
        
        return f"🎵 Opened YouTube Music search for '{artist_or_song}'. Find the artist or song, then click the three dots menu and select 'Start radio' to create a station."
        
    except Exception as e:
        return f"Error creating YouTube Music station: {e}"


@tool
def search_song_lyrics(song_name: str, artist_name: str = None) -> str:
    """
    Searches for and returns song lyrics using Genius API.

    Args:
        song_name: Name of the song
        artist_name: Optional artist name for better accuracy
    """
    try:
        import lyricsgenius
        import os

        # Get Genius API token from environment
        # Note: User needs to set GENIUS_API_TOKEN in .env file
        # Get free token at: https://genius.com/api-clients
        genius_token = os.getenv('GENIUS_API_TOKEN')

        if not genius_token:
            # Fallback to web scraping approach
            return search_lyrics_web(song_name, artist_name)

        genius = lyricsgenius.Genius(genius_token)
        genius.verbose = False
        genius.remove_section_headers = True

        # Search for the song
        if artist_name:
            song = genius.search_song(song_name, artist_name)
        else:
            song = genius.search_song(song_name)

        if song:
            result = f"🎵 **{song.title}** by {song.artist}\n\n"
            result += f"📝 **Lyrics:**\n\n{song.lyrics[:1500]}"  # Truncate if too long

            if len(song.lyrics) > 1500:
                result += "\n\n... [Lyrics truncated. Full lyrics available at Genius.com]"

            return result
        else:
            return f"Could not find lyrics for '{song_name}'" + (f" by {artist_name}" if artist_name else "")

    except Exception as e:
        return f"Error searching for lyrics: {e}. You may need to set GENIUS_API_TOKEN in your .env file. Get a free token at https://genius.com/api-clients"


@tool
def search_lyrics_web(song_name: str, artist_name: str = None) -> str:
    """
    Searches for song lyrics using web scraping (no API key required).

    Args:
        song_name: Name of the song
        artist_name: Optional artist name for better accuracy
    """
    try:
        # Construct search query for Genius
        if artist_name:
            search_query = f"{song_name} {artist_name} lyrics genius"
        else:
            search_query = f"{song_name} lyrics genius"

        encoded_query = urllib.parse.quote_plus(search_query)

        # Search on Google to find Genius lyrics page
        search_url = f"https://www.google.com/search?q={encoded_query}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find Genius URL from search results
        genius_link = None
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if 'genius.com' in href and '/lyrics' not in href:
                # Extract actual URL from Google's redirect
                if 'url?q=' in href:
                    genius_link = href.split('url?q=')[1].split('&')[0]
                    genius_link = urllib.parse.unquote(genius_link)
                    break

        if genius_link:
            # Open the Genius page in browser for user to view
            webbrowser.open(genius_link)

            if artist_name:
                return f"🎵 Found lyrics for '{song_name}' by {artist_name}! Opening Genius.com in your browser where you can view the full lyrics."
            else:
                return f"🎵 Found lyrics for '{song_name}'! Opening Genius.com in your browser where you can view the full lyrics."
        else:
            # Fallback to direct Genius search
            if artist_name:
                search_url = f"https://genius.com/search?q={urllib.parse.quote_plus(song_name + ' ' + artist_name)}"
            else:
                search_url = f"https://genius.com/search?q={urllib.parse.quote_plus(song_name)}"

            webbrowser.open(search_url)
            return f"🎵 Opening Genius.com search for '{song_name}'. Click on the correct song to view lyrics!"

    except Exception as e:
        return f"Error searching for lyrics: {e}"


@tool
def play_genre_playlist(genre: str, platform: str = "youtube_music") -> str:
    """
    Plays a playlist of a specific music genre.

    Args:
        genre: Music genre (e.g., "jazz", "rock", "classical", "pop", "hip hop", "electronic")
        platform: Platform to use ("youtube_music", "youtube", or "spotify")
    """
    try:
        sp, _ = _get_spotify_client()
        if platform == "spotify" and sp:
            # Search for genre playlist on Spotify
            results = sp.search(q=f"{genre}", type='playlist', limit=1)
            playlists = results['playlists']['items']

            if playlists:
                playlist_uri = playlists[0]['uri']
                playlist_name = playlists[0]['name']

                # Check for active devices
                devices = sp.devices()
                if not devices or not devices['devices']:
                    return "No active Spotify device found. Please open Spotify on one of your devices."

                active_device_id = None
                for device in devices['devices']:
                    if device['is_active']:
                        active_device_id = device['id']
                        break

                if not active_device_id:
                    active_device_id = devices['devices'][0]['id']

                sp.start_playback(device_id=active_device_id, context_uri=playlist_uri)
                return f"🎵 Playing {genre} playlist: '{playlist_name}' on Spotify!"
            else:
                return f"Could not find a {genre} playlist on Spotify."

        elif platform == "youtube_music":
            # Open YouTube Music with genre search
            encoded_genre = urllib.parse.quote_plus(f"{genre} music playlist")
            url = f"https://music.youtube.com/search?q={encoded_genre}"
            webbrowser.open(url)
            return f"🎵 Opened YouTube Music with {genre} playlists. Click on a playlist to start listening!"

        else:  # youtube
            # Open YouTube with genre playlist
            encoded_genre = urllib.parse.quote_plus(f"{genre} music playlist")
            url = f"https://www.youtube.com/results?search_query={encoded_genre}"
            webbrowser.open(url)
            return f"🎵 Opened YouTube with {genre} playlists. Click on a playlist to start listening!"

    except Exception as e:
        return f"Error playing genre playlist: {e}"


@tool
def play_mood_music(mood: str) -> str:
    """
    Plays music that matches a specific mood or activity.

    Args:
        mood: Mood or activity (e.g., "relaxing", "workout", "focus", "party", "sleep", "study")
    """
    try:
        # Map moods to search queries
        mood_queries = {
            "relaxing": "relaxing chill music",
            "workout": "workout gym motivation music",
            "focus": "focus concentration study music",
            "party": "party dance music",
            "sleep": "sleep ambient music",
            "study": "study focus lofi music",
            "happy": "happy upbeat music",
            "sad": "sad emotional music",
            "romantic": "romantic love songs",
            "energetic": "energetic upbeat music"
        }

        search_query = mood_queries.get(mood.lower(), f"{mood} music")

        # Try Spotify first if available
        sp, _ = _get_spotify_client()
        if sp:
            try:
                results = sp.search(q=search_query, type='playlist', limit=1)
                playlists = results['playlists']['items']

                if playlists:
                    playlist_uri = playlists[0]['uri']
                    playlist_name = playlists[0]['name']

                    devices = sp.devices()
                    if devices and devices['devices']:
                        active_device_id = None
                        for device in devices['devices']:
                            if device['is_active']:
                                active_device_id = device['id']
                                break

                        if not active_device_id:
                            active_device_id = devices['devices'][0]['id']

                        sp.start_playback(device_id=active_device_id, context_uri=playlist_uri)
                        return f"🎵 Playing {mood} music: '{playlist_name}' on Spotify!"
            except:
                pass

        # Fallback to YouTube Music
        encoded_query = urllib.parse.quote_plus(search_query + " playlist")
        url = f"https://music.youtube.com/search?q={encoded_query}"
        webbrowser.open(url)
        return f"🎵 Opened YouTube Music with {mood} music playlists. Click on a playlist to start listening!"

    except Exception as e:
        return f"Error playing mood music: {e}"


@tool
def discover_new_music(based_on: str = None) -> str:
    """
    Discovers new music recommendations.

    Args:
        based_on: Optional artist or genre to base recommendations on
    """
    try:
        sp, _ = _get_spotify_client()
        if sp:
            try:
                if based_on:
                    # Search for the artist/genre
                    results = sp.search(q=based_on, type='artist', limit=1)
                    if results['artists']['items']:
                        artist_id = results['artists']['items'][0]['id']

                        # Get related artists
                        related = sp.artist_related_artists(artist_id)

                        result = f"🎵 **Artists similar to {based_on}:**\n\n"
                        for i, artist in enumerate(related['artists'][:5], 1):
                            result += f"{i}. {artist['name']}\n"

                        # Open Spotify artist radio
                        devices = sp.devices()
                        if devices and devices['devices']:
                            return result + f"\n\nTip: Use 'create radio station based on {based_on}' to start a discovery playlist!"

                        return result
                else:
                    # Get user's top artists (requires additional auth scope)
                    # For now, just open Spotify's Discover page
                    webbrowser.open("https://open.spotify.com/genre/discover-page")
                    return "🎵 Opened Spotify's Discover page where you can find personalized music recommendations!"
            except:
                pass

        # Fallback to YouTube Music
        if based_on:
            encoded_query = urllib.parse.quote_plus(f"music like {based_on}")
            url = f"https://music.youtube.com/search?q={encoded_query}"
        else:
            url = "https://music.youtube.com/explore"

        webbrowser.open(url)
        return "🎵 Opened YouTube Music's explore/discovery page where you can find new music!"

    except Exception as e:
        return f"Error discovering new music: {e}"


# This is the list of tools that will be passed to the agent
music_tools = [
    # Spotify tools
    search_and_play_song,
    next_song,
    previous_song,
    pause_music,
    resume_music,
    set_volume,
    get_current_song,

    # Enhanced YouTube tools with auto-play (uses existing logged-in browser)
    auto_play_youtube_music_song,  # BEST for YouTube Music - uses logged-in browser
    auto_play_youtube_song,         # BEST for YouTube - uses logged-in browser
    play_music_smart,  # Primary smart tool that tries multiple platforms
    play_youtube_music_direct,  # Auto-play with YouTube Music backup
    play_on_youtube_music,
    play_on_youtube,
    open_youtube_music,
    search_youtube_music,
    play_youtube_music_playlist,
    open_youtube_music_library,
    create_youtube_music_station,

    # New enhanced tools
    search_song_lyrics,
    search_lyrics_web,
    play_genre_playlist,
    play_mood_music,
    discover_new_music
]