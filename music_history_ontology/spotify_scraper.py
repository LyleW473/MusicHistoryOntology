import json
import os
import time
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException


def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


# Load environment variables from .env file
load_dotenv()

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise Exception("Missing Spotify credentials in environment variables.")


def spotify_request(func, *args, max_retries=3, **kwargs):
    retries = 0
    while True:
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 1))
                time.sleep(retry_after)
                retries += 1
                if retries > max_retries:
                    raise
            else:
                raise


def get_spotify_client():
    auth_manager = SpotifyClientCredentials(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)
    return sp


def get_artist_data(artist_name):
    sp = get_spotify_client()

    def search_artist():
        return sp.search(q=artist_name, type="artist", limit=1)

    results = spotify_request(search_artist)
    items = results.get("artists", {}).get("items", [])
    if not items:
        return {}
    return items[0]


def get_all_artist_albums(artist_id):
    sp = get_spotify_client()
    albums = []
    offset = 0
    limit = 50
    while True:

        def fetch_albums():
            return sp.artist_albums(
                artist_id, album_type="album", offset=offset, limit=limit
            )

        result = spotify_request(fetch_albums)
        items = result.get("items", [])
        albums.extend(items)
        if result.get("next") is None:
            break
        offset += limit
    return albums


def get_all_album_tracks(album_id):
    sp = get_spotify_client()
    tracks = []
    offset = 0
    limit = 50
    while True:

        def fetch_tracks():
            return sp.album_tracks(album_id, offset=offset, limit=limit)

        result = spotify_request(fetch_tracks)
        items = result.get("items", [])
        tracks.extend(items)
        if result.get("next") is None:
            break
        offset += limit

    return tracks


def get_related_artists(artist_id):
    sp = get_spotify_client()

    def fetch_related():
        return sp.artist_related_artists(artist_id)

    try:
        result = spotify_request(fetch_related)
        return result.get("artists", [])
    except SpotifyException as e:
        if e.http_status == 404:
            # If the endpoint returns 404, return an empty list
            return []
        else:
            raise


def process_artist(artist_name):
    artist_data = get_artist_data(artist_name)
    if not artist_data:
        return {"error": f"Artist '{artist_name}' not found"}
    artist_id = artist_data.get("id")
    # Get all albums with pagination
    albums = get_all_artist_albums(artist_id)
    detailed_albums = []
    for album in albums:
        album_id = album.get("id")
        # For each album, retrieve all tracks with detailed info
        tracks = get_all_album_tracks(album_id)
        album["tracks"] = tracks
        detailed_albums.append(album)
    # Retrieve related artists
    related_artists = get_related_artists(artist_id)
    return {
        "artist": artist_data,
        "albums": detailed_albums,
        "related_artists": related_artists,
    }


def process_artists(artist_list):
    all_data = {}
    for artist in artist_list:
        print(f"Processing {artist}...")
        data = process_artist(artist)
        all_data[artist] = data
    return all_data


def save_data_to_json(data, filename="spotify_data.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def main():
    # Provide a list of artists to process
    artists = ["Punkto"]
    all_data = process_artists(artists)
    save_data_to_json(all_data)
    print("Data saved to spotify_data.json")


if __name__ == "__main__":
    main()
