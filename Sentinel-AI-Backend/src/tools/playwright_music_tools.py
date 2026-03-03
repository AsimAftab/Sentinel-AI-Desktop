# src/tools/playwright_music_tools.py

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from langchain_core.tools import tool
import atexit
import threading
import time
import os

# Global browser instance (reused across calls for efficiency)
_playwright_instance = None
_browser = None
_context = None
_page = None
_browser_lock = threading.Lock()


def _get_browser():
    """Get or create a persistent browser instance (thread-safe)."""
    global _playwright_instance, _browser, _context, _page

    with _browser_lock:
        if _browser is None:
            _playwright_instance = sync_playwright().start()
            _browser = _playwright_instance.chromium.launch(headless=False)  # Set to True for headless
            _context = _browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            _page = _context.new_page()

    return _page


def _close_browser():
    """Close the browser instance (thread-safe)."""
    global _playwright_instance, _browser, _context, _page

    with _browser_lock:
        if _page:
            try:
                _page.close()
            except Exception:
                pass
            _page = None
        if _context:
            try:
                _context.close()
            except Exception:
                pass
            _context = None
        if _browser:
            try:
                _browser.close()
            except Exception:
                pass
            _browser = None
        if _playwright_instance:
            try:
                _playwright_instance.stop()
            except Exception:
                pass
            _playwright_instance = None


# Ensure browser is cleaned up when the process exits
atexit.register(_close_browser)


@tool
def playwright_play_youtube_music(
    song_name: str, artist_name: str = None, auto_play: bool = True
) -> str:
    """
    [RECOMMENDED for YOUTUBE MUSIC] Plays songs on YOUTUBE MUSIC with TRUE AUTO-PLAY.
    Uses browser automation - song starts playing automatically, NO manual clicking!

    IMPORTANT: This is specifically for YouTube Music (music.youtube.com), NOT regular YouTube!
    For regular YouTube videos, use playwright_play_youtube instead.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
        auto_play: Whether to automatically click the play button (default: True)
    """
    try:
        page = _get_browser()

        # Construct search query
        if artist_name:
            search_query = f"{song_name} {artist_name}"
        else:
            search_query = song_name

        # Navigate to YouTube Music
        page.goto("https://music.youtube.com/", wait_until="networkidle", timeout=30000)

        # Wait for and click the search button
        try:
            search_button = page.locator('ytmusic-search-box button[aria-label*="Search"]').first
            search_button.wait_for(state="visible", timeout=10000)
            search_button.click()
        except Exception:
            # Alternative: try finding search input directly
            pass

        # Type in the search box
        search_input = page.locator(
            'input[placeholder="Search songs, albums, artists, podcasts"]'
        ).first
        search_input.wait_for(state="visible", timeout=10000)
        search_input.fill(search_query)
        search_input.press("Enter")

        if auto_play:
            # Find and click the first song result
            try:
                # Try multiple selectors for the first song
                first_song = page.locator("ytmusic-responsive-list-item-renderer").first
                first_song.wait_for(state="visible", timeout=10000)

                # Click the play button or the song itself
                play_button = first_song.locator('button[aria-label*="Play"]').first
                if play_button.is_visible():
                    play_button.click()
                else:
                    # If no play button, click the song title
                    first_song.click()

                return (
                    f"🎵 Successfully found and playing '{song_name}'"
                    + (f" by {artist_name}" if artist_name else "")
                    + " on YouTube Music! The song is now playing automatically."
                )

            except Exception as e:
                return f"🎵 Opened YouTube Music and searched for '{search_query}'. Search results are displayed, but auto-play encountered an issue: {e}. You can manually click the first result to play."
        else:
            return f"🎵 Opened YouTube Music and searched for '{search_query}'. The first result should be your song - click it to play!"

    except PlaywrightTimeoutError:
        return f"⏰ Timeout while loading YouTube Music. Please check your internet connection and try again."

    except Exception as e:
        return f"❌ Error with Playwright automation: {e}. Falling back to manual browser opening."


@tool
def playwright_play_youtube(song_name: str, artist_name: str = None, auto_play: bool = True) -> str:
    """
    [RECOMMENDED for REGULAR YOUTUBE] Plays songs on REGULAR YOUTUBE with TRUE AUTO-PLAY.
    Uses browser automation - video starts playing automatically, NO manual clicking!

    IMPORTANT: This is specifically for regular YouTube (youtube.com), NOT YouTube Music!
    For YouTube Music, use playwright_play_youtube_music instead.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to improve search accuracy
        auto_play: Whether to automatically click the first video (default: True)
    """
    try:
        page = _get_browser()

        # Construct search query
        if artist_name:
            search_query = f"{song_name} {artist_name} official audio"
        else:
            search_query = f"{song_name} official audio"

        # Navigate to YouTube with search query
        search_url = (
            f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
        )
        page.goto(search_url, wait_until="networkidle", timeout=30000)

        if auto_play:
            try:
                # Find the first video result (not ad, not short)
                video_link = page.locator("a#video-title").first
                video_link.wait_for(state="visible", timeout=10000)

                # Get the video title for confirmation
                video_title = video_link.get_attribute("title")

                # Click the video
                video_link.click()

                # Wait for the video player to become interactive
                try:
                    page.wait_for_selector(".ytp-play-button", timeout=8000)
                except Exception:
                    pass  # Player may render differently; proceed anyway

                return f"🎥 Successfully found and playing '{video_title}' on YouTube! The video is now playing automatically."

            except Exception as e:
                return f"🎥 Opened YouTube with search results for '{search_query}'. Auto-play encountered an issue: {e}. You can manually click the first video to play."
        else:
            return f"🎥 Opened YouTube and searched for '{search_query}'. Click the first video to play!"

    except PlaywrightTimeoutError:
        return f"⏰ Timeout while loading YouTube. Please check your internet connection and try again."

    except Exception as e:
        return f"❌ Error with Playwright automation: {e}"


@tool
def playwright_control_youtube_music(action: str) -> str:
    """
    Controls YouTube Music playback using Playwright automation.

    Args:
        action: The control action to perform. Options:
            - "play" or "resume": Resume playback
            - "pause": Pause playback
            - "next": Skip to next song
            - "previous": Go to previous song
            - "like": Like the current song
            - "dislike": Dislike the current song
    """
    try:
        page = _get_browser()

        # Make sure we're on YouTube Music
        if "music.youtube.com" not in page.url:
            return "⚠️ YouTube Music is not currently open. Please play a song first."

        action = action.lower().strip()

        if action in ["play", "resume"]:
            # Click the play button
            play_button = page.locator('button[aria-label*="Play"]').first
            if play_button.is_visible(timeout=5000):
                play_button.click()
                return "▶️ Resumed playback on YouTube Music."
            else:
                return "⚠️ Play button not found. Music might already be playing."

        elif action == "pause":
            # Click the pause button
            pause_button = page.locator('button[aria-label*="Pause"]').first
            if pause_button.is_visible(timeout=5000):
                pause_button.click()
                return "⏸️ Paused playback on YouTube Music."
            else:
                return "⚠️ Pause button not found. Music might already be paused."

        elif action == "next":
            # Click the next button
            next_button = page.locator('button[aria-label*="Next"]').first
            next_button.wait_for(state="visible", timeout=5000)
            next_button.click()
            page.wait_for_timeout(500)  # Brief wait for track transition
            return "⏭️ Skipped to next song on YouTube Music."

        elif action == "previous":
            # Click the previous button
            prev_button = page.locator('button[aria-label*="Previous"]').first
            prev_button.wait_for(state="visible", timeout=5000)
            prev_button.click()
            page.wait_for_timeout(500)  # Brief wait for track transition
            return "⏮️ Went back to previous song on YouTube Music."

        elif action == "like":
            # Click the like button
            like_button = page.locator('button[aria-label*="Like"]').first
            like_button.wait_for(state="visible", timeout=5000)
            like_button.click()
            return "👍 Liked the current song on YouTube Music."

        elif action == "dislike":
            # Click the dislike button
            dislike_button = page.locator('button[aria-label*="Dislike"]').first
            dislike_button.wait_for(state="visible", timeout=5000)
            dislike_button.click()
            return "👎 Disliked the current song on YouTube Music."

        else:
            return f"❌ Unknown action: {action}. Valid actions are: play, pause, next, previous, like, dislike"

    except PlaywrightTimeoutError:
        return f"⏰ Timeout while trying to {action}. The control button might not be visible."

    except Exception as e:
        return f"❌ Error controlling YouTube Music: {e}"


@tool
def playwright_get_current_song() -> str:
    """
    Gets information about the currently playing song on YouTube Music using Playwright.
    """
    try:
        page = _get_browser()

        # Make sure we're on YouTube Music
        if "music.youtube.com" not in page.url:
            return "⚠️ YouTube Music is not currently open."

        # Get song title
        title_element = page.locator(".title.style-scope.ytmusic-player-bar").first
        title = title_element.inner_text(timeout=5000) if title_element.is_visible() else "Unknown"

        # Get artist name
        artist_element = page.locator(".byline.style-scope.ytmusic-player-bar a").first
        artist = (
            artist_element.inner_text(timeout=5000) if artist_element.is_visible() else "Unknown"
        )

        # Get time info
        time_info = page.locator(".time-info.style-scope.ytmusic-player-bar").first
        time_text = time_info.inner_text(timeout=5000) if time_info.is_visible() else "Unknown"

        return f"🎵 Currently playing: '{title}' by {artist}\n⏱️ Time: {time_text}"

    except Exception as e:
        return f"❌ Error getting current song info: {e}"


@tool
def playwright_create_radio_station(artist_or_song: str) -> str:
    """
    Creates a radio station on YouTube Music based on an artist or song using Playwright.

    Args:
        artist_or_song: Artist name or song to base the radio on
    """
    try:
        page = _get_browser()

        # Navigate to YouTube Music
        page.goto("https://music.youtube.com/", wait_until="networkidle", timeout=30000)

        # Search for the artist/song
        search_input = page.locator(
            'input[placeholder="Search songs, albums, artists, podcasts"]'
        ).first
        search_input.wait_for(state="visible", timeout=10000)
        search_input.fill(artist_or_song)
        search_input.press("Enter")

        # Click on the first result (wait_for handles the page load)
        first_result = page.locator("ytmusic-responsive-list-item-renderer").first
        first_result.wait_for(state="visible", timeout=10000)
        first_result.click()

        # Try to find and click the "Start radio" button
        try:
            radio_button = page.locator('button[aria-label*="Start radio"]').first
            if radio_button.is_visible(timeout=5000):
                radio_button.click()
                return f"📻 Started radio station based on '{artist_or_song}' on YouTube Music!"
            else:
                # Try the three-dot menu
                menu_button = page.locator('button[aria-label="Menu"]').first
                menu_button.wait_for(state="visible", timeout=5000)
                menu_button.click()

                radio_option = page.locator('text="Start radio"').first
                if radio_option.is_visible(timeout=3000):
                    radio_option.click()
                    return f"📻 Started radio station based on '{artist_or_song}' on YouTube Music!"
                else:
                    return f"🎵 Opened '{artist_or_song}' on YouTube Music. Look for the 'Start radio' option in the menu."
        except Exception:
            return f"🎵 Opened '{artist_or_song}' on YouTube Music. Look for the 'Start radio' option in the menu."

    except Exception as e:
        return f"❌ Error creating radio station: {e}"


@tool
def close_music_browser() -> str:
    """
    Closes the Playwright browser instance used for music playback.
    Use this when you're done listening to music to free up resources.
    """
    try:
        _close_browser()
        return "✅ Closed the music browser successfully."
    except Exception as e:
        return f"❌ Error closing browser: {e}"


# Playwright music tools list
playwright_music_tools = [
    playwright_play_youtube_music,
    playwright_play_youtube,
    playwright_control_youtube_music,
    playwright_get_current_song,
    playwright_create_radio_station,
    close_music_browser,
]
