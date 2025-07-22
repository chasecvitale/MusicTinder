# Chase Vitale
# Music Tinder

# Import statements
import os
import json
from dotenv import load_dotenv
from tqdm import tqdm
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import vlc
import yt_dlp
import time

#######################################################################################

# Initializations

# Set up Spotify client with OAuth for user-level permissions
load_dotenv()

# Optionally delete cache to force re-login
# if os.path.exists(".cache"):
#    os.remove(".cache")

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-library-read playlist-modify-private playlist-modify-public",
    cache_path=None
))

# Set up genre classification json
with open('genres.json', 'r') as f:
    GENRE_CATEGORIES = json.load(f)

# Create VLC instance with plugin path
instance = vlc.Instance()

# Set up URL fetching
ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
ydl = yt_dlp.YoutubeDL(ydl_opts)

#######################################################################################

# Main functions

# Fetches all of the user's liked tracks.
# Input: sp (defined)
# Output: List of tracks
def get_all_liked_tracks(sp):

    # Calculates how many liked songs the user has in total
    results = sp.current_user_saved_tracks(limit=1)
    total_liked_tracks = results['total']

    # Initializes a progress bar for parsing liked songs
    pbar = tqdm(total=(total_liked_tracks), desc="Fetching liked tracks")

    # Parses through the user's liked songs and saves them to a list
    tracks = []
    offset = 0
    limit = 50

    while offset < 1:
    #while offset < total_liked_tracks:
        response = sp.current_user_saved_tracks(limit=limit, offset=offset, market=None)
        items = response['items']
        if not items:
            break
        tracks.extend(items)
        offset += len(items)
        pbar.update(len(items))

    # Closes the progress bar and returns the liked songs
    pbar.close()
    return tracks

# Takes a subgenre and returns the main genre using the genres.json file
# Input: string of subgenre
# Output: String of genre
def subgenre_to_genre(subgenre):

    # Returns genre classification
    for parent, subgenres in GENRE_CATEGORIES.items():
        if subgenre in subgenres:
            return parent
    return "unknown"

# Creates a list of artists that appear on a list of tracks
# Input: List of tracks
# Output: List of artists
def get_artists_from_tracks(tracks):

    # Creates an empty set
    artists = set()

    # Iterates through all liked songs and puts the artists into the set
    for track in tracks:
        artist_list = track["track"]["artists"]
        for artist in artist_list:
            artists.add(artist["name"])

    return list(artists)

# Creates a set with all of the artist ids from a list of tracks
# Input: A list of tracks
# Output: A list of artist ids
def get_artist_ids_from_tracks(tracks):

    # Creates an empty set
    artist_ids = set()

    # Iterates through all liked songs and puts the artists into the set
    for track in tracks:
        artist_list = track["track"]["artists"]
        for artist in artist_list:
            artist_ids.add(artist["id"])

    return list(artist_ids)

# Creates a dictionary with the artist and their genres (converted to main genre)
# Input: sp (prefefined); list of artist ids
# Output: a dictionary of artist and genres
def get_artist_genres(sp, artist_ids):
    genres_by_artist = {}

    # Initializes a progress bar for parsing artist genres
    pbar = tqdm(total=(len(artist_ids)), desc="Fetching artist genres")

    # Fetch artists in batches of 50
    for i in range(0, len(artist_ids), 50):
        batch = artist_ids[i:i+50]
        response = sp.artists(batch)

        # Iterates through the responses one at a time
        for artist in response["artists"]:

            # Converts subgenres to main genres
            main_genres = []

            for genre in artist["genres"]:
                main_genres.append(subgenre_to_genre(genre))

            # Creates the dictionary
            genres_by_artist[artist["id"]] = {
                'name': artist["name"],
                'genres': main_genres
            }
        pbar.update(len(batch))
    
    pbar.close()
    return genres_by_artist

# Creates a dictionary with liked songs and their genre
# Input: list of tracks; dictionary of artists and genres
# Output: dictionary 
def liked_songs_genre(tracks, genres_by_artist):
    songs_genres = {
        "country": [], 
        "hip-hop": [],
        "rap": [],
        "jazz": [],
        "blues": [],
        "rock": [],
        "soul": [],
        "classical": [],
        "folk": [],
        "funk": [],
        "electronic": [],
        "latin": [],
        "r&b": [],
        "reggae": [],
        "traditional": [],
        "pop": [],
        "indie": [],
        "theatre": [],
        "dance": [],
        "unknown": []
    }

    # Initializes a progress bar for parsing artist genres
    pbar = tqdm(total=(len(tracks)), desc="Sorting songs by genre")

    for track in tracks:
        artist_ids = [artist["id"] for artist in track["track"]["artists"]]
        added_genres = set()

        for artist_id in artist_ids:
            if artist_id in genres_by_artist:
                for genre in genres_by_artist[artist_id]["genres"]:
                    if genre in songs_genres and genre not in added_genres:
                        songs_genres[genre].append(track)
                        added_genres.add(genre)
        pbar.update(1)

    pbar.close()
    return songs_genres

# Get the URL of the YouTube video that matches the query
# Input: string for search
# Output: string of URL
def get_stream_url(query):
    result = ydl.extract_info(f"ytsearch1:{query}", download=False)
    return result['entries'][0]['url']

# Creates a list of song names, artists, and stream urls based on the given tracks
# Input: list of tracks
# Output: 
def get_all_track_info(tracks):
    songs = []
    for track in tracks:
        track_info = []
        track_uri = track["track"]["uri"]
        track_name = track["track"]["name"]
        artist_names = "".join(artist["name"] for artist in track["track"]["artists"])
        search_query = f"{track_name}, {artist_names}"
        track_url = get_stream_url(search_query)
        track_image = track["track"]["album"]["images"][0]["url"]
        track_info = [track_uri, track_name, artist_names, track_url, track_image]
        songs.append(track_info)
    return songs

# Plays the audio at the URL
# Input: string of URL
# Output: none / audio plays
def play_stream_url(stream_url):
    global player
    if player:
        player.stop()
    player = instance.media_player_new()
    media = instance.media_new(stream_url)
    player.set_media(media)
    player.play()
    return player

# Locates and plays the audio for a specific track object
# Input: track
# Output: none/audio
def play_stream_track(track):
    track_name = track["track"]["name"]
    artist_names = ", ".join(artist["name"] for artist in track["track"]["artists"])
    search_query = f"{track_name} {artist_names}"
    stream_url = get_stream_url(search_query)
    play_stream_url(stream_url)

# Creates a new playlist with given name
# Input: sp, user_id, and playlist description
# Output: playlist id
def create_playlist(sp, name, description):
    user_id = sp.current_user()["id"]
    playlist = sp.user_playlist_create(user=user_id, name=name, public=False, description=description)
    return playlist["id"]

# Adds the given tracks to the playlist
# Input: sp, playlist id, and track uris
# Output: none
def add_to_playlist(sp, playlist_id, track_uris):
    # Spotify API allows adding max 100 tracks per request
    for i in range(0, len(track_uris), 100):
        batch = track_uris[i:i+100]
        sp.playlist_add_items(playlist_id, batch)