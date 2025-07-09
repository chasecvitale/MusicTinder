import os
import json
from dotenv import load_dotenv
from tqdm import tqdm
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Set up Spotify client with OAuth for user-level permissions
load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
    scope="user-library-read"
))

# Set up genre classification json
with open('genres.json', 'r') as f:
    GENRE_CATEGORIES = json.load(f)

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

    while offset < total_liked_tracks:
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
        "unknown": []
    }

    for track in tracks:
        artist_ids = [artist["id"] for artist in track["track"]["artists"]]
        added_genres = set()

        for artist_id in artist_ids:
            if artist_id in genres_by_artist:
                for genre in genres_by_artist[artist_id]["genres"]:
                    if genre in songs_genres and genre not in added_genres:
                        songs_genres[genre].append(track)
                        added_genres.add(genre)

    return songs_genres

# Takes the dictionary of genres and songs and has the user sort the unknowns
# Input: dictionary of songs and genres
# Output: none
def sort_unknowns(songs_genres):
    unknown = songs_genres["unknown"]
    for track in unknown:
        print("Enter the corresponding number to place the track into the correct genre:")
        print(
            "1. Country\t10. Funk\n" \
            "2. Hip-Hop\t11. Electronic\n" \
            "3. Rap\t\t12. Latin\n" \
            "4. Jazz\t\t13. R&B\n" \
            "5. Blues\t14. Reggae\n" \
            "6. Rock\t\t15. Traditional\n" \
            "7. Soul\t\t16. Pop\n" \
            "8. Classical\t17. Indie\n" \
            "9. Folk\t\t18. Theater\n"
        )
        print("Enter anything else to stop.")
        

get_all_liked_tracks(sp)