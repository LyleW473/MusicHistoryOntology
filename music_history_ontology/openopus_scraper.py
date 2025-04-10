import json
import time
import requests

BASE_URL = "https://api.openopus.org"


def opus_request(url, params=None, max_retries=3):
    """Make a GET request to the Open Opus API with a simple backoff-retry strategy."""
    retries = 0
    while True:
        response = requests.get(url, params=params)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 1))
            time.sleep(retry_after)
            retries += 1
            if retries > max_retries:
                response.raise_for_status()
            continue
        response.raise_for_status()
        return response.json()


def get_composer_by_search(query):
    """
    Search for a composer by name.
    Uses the /composer/list/search/<query>.json endpoint.
    Returns the first matching composer.
    """
    url = f"{BASE_URL}/composer/list/search/{query}.json"
    data = opus_request(url)
    composers = data.get("composers", [])
    if composers:
        return composers[0]
    return None


def get_composer_genres(composer_id):
    """
    Get genres associated with a composer.
    Uses the /genre/list/composer/<composer_id>.json endpoint.
    """
    url = f"{BASE_URL}/genre/list/composer/{composer_id}.json"
    data = opus_request(url)
    return data.get("genres", [])


def get_composer_works(composer_id):
    """
    Get all works by a composer.
    Uses the /work/list/composer/<composer_id>/genre/all.json endpoint.
    """
    url = f"{BASE_URL}/work/list/composer/{composer_id}/genre/all.json"
    data = opus_request(url)
    return data.get("works", [])


def process_composer(composer_name):
    """
    Process a single composer:
      - Search for the composer by name.
      - Fetch genres and works.
      - Combine data into one dictionary.
    """
    composer_data = get_composer_by_search(composer_name)
    if composer_data is None:
        return {"error": f"Composer '{composer_name}' not found"}

    composer_id = composer_data.get("id")
    # Fetch additional data
    genres = get_composer_genres(composer_id)
    works = get_composer_works(composer_id)

    composer_data["genres"] = genres
    composer_data["works"] = works
    return composer_data


def process_composers(composer_list):
    """
    Process a list of composers.
    Returns a dictionary keyed by composer name.
    """
    all_data = {}
    for composer in composer_list:
        print(f"Processing {composer}...")
        data = process_composer(composer)
        all_data[composer] = data
    return all_data


def save_data_to_json(data, filename="openopus_data.json"):
    """
    Save the collected data to a JSON file.
    """
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def main():
    # Define a list of composers to ingest data for
    composers = ["Bach", "Beethoven", "Mozart"]
    all_data = process_composers(composers)
    save_data_to_json(all_data)
    print("Data saved to openopus_data.json")


if __name__ == "__main__":
    main()
