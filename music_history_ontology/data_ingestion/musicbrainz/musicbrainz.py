import requests
from ratelimit import limits, sleep_and_retry

MUSICBRAINZ_API_URL = "https://musicbrainz.org/ws/2/"
ONE_SECOND = 1


class MusicBrainzClient:
    def __init__(
        self,
        app_name="MusicOntologyPopulator",
        app_version="0.1",
        contact="contact@example.com",
    ):
        self.headers = {
            "User-Agent": f"{app_name}/{app_version} ( {contact} )",
            "Accept": "application/json",
        }
        self.base_url = MUSICBRAINZ_API_URL

    @sleep_and_retry
    @limits(calls=1, period=ONE_SECOND)
    def _request(self, endpoint, params=None):
        """Makes a rate-limited request to the MusicBrainz API."""
        if params is None:
            params = {}
        params["fmt"] = "json"  # Ensure JSON format

        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            # Consider more robust error handling/logging
            return None
        except requests.exceptions.JSONDecodeError:
            print(f"Error decoding JSON response from {url}")
            print(
                f"Response text: {response.text[:500]}..."
            )  # Log part of the response
            return None

    def search_artist(self, name, limit=1):
        """Searches for an artist by name."""
        params = {"query": name, "limit": limit}
        return self._request("artist", params=params)

    def search_release_group(self, title, artist_name=None, limit=1, type="album"):
        """Searches for a release group (album, single, EP) by title."""
        query_parts = [f'releasegroup:"{title}"']
        if artist_name:
            query_parts.append(f'artistname:"{artist_name}"')
        if type:
            query_parts.append(
                f'primarytype:"{type.capitalize()}"'
            )  # e.g., Album, Single

        query = " AND ".join(query_parts)
        params = {"query": query, "limit": limit}
        return self._request("release-group", params=params)

    def search_work(self, name, artist_name=None, limit=1):
        """Searches for a work (e.g., a song as a conceptual entity)."""
        query_parts = [f'work:"{name}"']
        if artist_name:
            query_parts.append(f'artist:"{artist_name}"')
        query = " AND ".join(query_parts)
        params = {"query": query, "limit": limit}
        return self._request("work", params=params)

    def search_genre(self, name, limit=5):
        """Searches for a genre (tag) by name."""
        # MusicBrainz uses 'tags' for genres
        params = {"query": name, "limit": limit}
        return self._request("tag", params=params)  # Note: Using the tag endpoint

    def search_instrument(self, name, limit=1):
        """Searches for an instrument by name."""
        params = {"query": name, "limit": limit}
        return self._request("instrument", params=params)

    def search_event(self, name, limit=1):
        """Searches for an event by name."""
        params = {"query": name, "limit": limit}
        return self._request("event", params=params)

    def search_ensemble(self, name, limit=1):
        """Searches for an ensemble (group artist type) by name."""
        query = f'artist:"{name}" AND type:"Group"'
        params = {"query": query, "limit": limit}
        return self._request(
            "artist", params=params
        )  # Ensembles are artists of type 'Group'

    # --- Lookup methods (by MBID) ---

    def lookup_artist(self, mbid, inc=[]):
        """Looks up an artist by MBID, optionally including related info."""
        params = {"inc": "+".join(inc)} if inc else {}
        return self._request(f"artist/{mbid}", params=params)

    def lookup_release_group(self, mbid, inc=[]):
        """Looks up a release group by MBID."""
        params = {"inc": "+".join(inc)} if inc else {}
        return self._request(f"release-group/{mbid}", params=params)

    def lookup_release(self, mbid, inc=[]):
        """Looks up a specific release (version of a release group) by MBID."""
        params = {"inc": "+".join(inc)} if inc else {}
        return self._request(f"release/{mbid}", params=params)

    def lookup_work(self, mbid, inc=[]):
        """Looks up a work by MBID."""
        params = {"inc": "+".join(inc)} if inc else {}
        return self._request(f"work/{mbid}", params=params)

    def lookup_instrument(self, mbid, inc=[]):
        """Looks up an instrument by MBID."""
        params = {"inc": "+".join(inc)} if inc else {}
        return self._request(f"instrument/{mbid}", params=params)

    def lookup_event(self, mbid, inc=[]):
        """Looks up an event by MBID."""
        params = {"inc": "+".join(inc)} if inc else {}
        return self._request(f"event/{mbid}", params=params)

    def lookup_genre(self, mbid, inc=[]):
        """Looks up a genre (tag) by MBID."""
        params = {"inc": "+".join(inc)} if inc else {}
        return self._request(f"tag/{mbid}", params=params)  # Using tag endpoint


# Example Usage (Optional - can be removed or run under if __name__ == '__main__')
if __name__ == "__main__":
    client = MusicBrainzClient()

    # Search Example
    print("Searching for Queen...")
    queen_search = client.search_artist("Queen")
    if queen_search and queen_search.get("artists"):
        queen_mbid = queen_search["artists"][0]["id"]
        print(f"Found Queen MBID: {queen_mbid}")

        # Lookup Example
        print("\nLooking up Queen details...")
        # Include artist relationships (members), release groups (albums), tags (genres)
        queen_details = client.lookup_artist(
            queen_mbid, inc=["artist-rels", "release-groups", "tags"]
        )
        if queen_details:
            print(f"Name: {queen_details.get('name')}")
            print(f"Type: {queen_details.get('type')}")
            print(f"Country: {queen_details.get('country')}")
            if queen_details.get("life-span"):
                print(
                    f"Life Span: {queen_details['life-span'].get('begin')} - {queen_details['life-span'].get('end', 'Present')}"
                )

            print("\nGenres (Tags):")
            if queen_details.get("tags"):
                for tag in queen_details["tags"][:5]:  # Show top 5 tags
                    print(f"- {tag.get('name')} (Count: {tag.get('count')})")

            print("\nSample Albums (Release Groups):")
            if queen_details.get("release-groups"):
                for rg in queen_details["release-groups"][:5]:  # Show top 5
                    print(
                        f"- {rg.get('title')} ({rg.get('primary-type')}, {rg.get('first-release-date')})"
                    )

            print("\nMembers (Sample):")
            if queen_details.get("relations"):
                for rel in queen_details["relations"]:
                    if rel.get("type") == "member of band":
                        member_artist = rel.get("artist")
                        if member_artist:
                            print(
                                f"- {member_artist.get('name')} ({rel.get('type')}, Active: {not rel.get('ended', False)})"
                            )
                            # You could add begin/end dates from rel if available

    else:
        print("Could not find Queen.")

    # Search Release Group Example
    print("\nSearching for album 'Abbey Road' by The Beatles...")
    abbey_road_search = client.search_release_group(
        "Abbey Road", artist_name="The Beatles", type="album"
    )
    if abbey_road_search and abbey_road_search.get("release-groups"):
        abbey_road_mbid = abbey_road_search["release-groups"][0]["id"]
        print(f"Found Abbey Road MBID: {abbey_road_mbid}")

        # Lookup Release Group
        abbey_road_details = client.lookup_release_group(
            abbey_road_mbid, inc=["artists", "releases", "tags"]
        )
        if abbey_road_details:
            print(f"Title: {abbey_road_details.get('title')}")
            print(f"Primary Type: {abbey_road_details.get('primary-type')}")
            print(f"First Release Date: {abbey_road_details.get('first-release-date')}")
            artist_credit = abbey_road_details.get("artist-credit", [])
            if artist_credit:
                print(f"Artist: {artist_credit[0]['name']}")

    # Search Instrument Example
    print("\nSearching for Saxophone...")
    sax_search = client.search_instrument("Saxophone")
    if sax_search and sax_search.get("instruments"):
        sax_mbid = sax_search["instruments"][0]["id"]
        print(f"Found Saxophone MBID: {sax_mbid}")
        sax_details = client.lookup_instrument(sax_mbid, inc=["tags"])
        if sax_details:
            print(f"Name: {sax_details.get('name')}")
            print(f"Type: {sax_details.get('type')}")
            print(
                f"Description: {sax_details.get('description', 'N/A')[:100]}..."
            )  # First 100 chars