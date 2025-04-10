import set_path
from rdflib import Namespace

# from scripts.musicbrainz import MusicBrainzClient # Changed to relative import
from music_history_ontology.data_ingestion.musicbrainz.musicbrainz import MusicBrainzClient  # Reverted to original import
from datetime import datetime
import re
import time  # For potential delays if needed beyond client rate limiting
import json  # Added
import os  # Added
from typing import Optional, Dict, Any  # Added for type hinting

# --- Pydantic Models ---
from pydantic import ValidationError

# Assuming pydantic_models.py is in a 'models' subdirectory relative to workspace root
try:
    # from models.pydantic_models import ( # Old import
    from models.pydantic_models import (  # Reverted to import from root models dir
        BaseEntity,
        Musician,
        MusicEnsemble,
        Instrument,
        MusicGenre,
        PerformanceEvent,
        Recording,
        Place,
        Country,
        RecordLabel,
        TimeInterval,
        MusicEnsembleMembership,
        MODEL_MAP,
    )
except ImportError:
    print(
        "Error: Could not import Pydantic models. Make sure 'models/pydantic_models.py' exists."
    )
    # Fallback or exit if models are critical
    exit()


# --- Configuration ---
# ONTOLOGY_FILE = "history_of_music_ontology.rdf" # No longer reading ontology file
# OUTPUT_FILE = "history_of_music_ontology.rdf" # No longer writing ontology file
DATA_DIR = "generated_data/musicbrainz"  # Directory to store JSON files
BASE_URI = "http://www.semanticweb.org/lianmatsuo/ontologies/2025/2/history_of_music#"  # Still useful for context
MB_BASE_URI = "http://musicbrainz.org/"

# --- Namespaces (keep HOM for context/potential future use in identifiers) ---
HOM = Namespace(BASE_URI)
# Standard namespaces might still be useful for datatypes like XSD.date
# Keep OWL.sameAs thinking? Yes, map mb_uri to 'sameAs' field.

# --- Smaller Data Lists for Testing (REDUCED FURTHER) ---
MUSICIANS_TEST = [
    "Wolfgang Amadeus Mozart",
    "Frédéric Chopin",
    "Ludwig van Beethoven",
    "Giuseppe Verdi",
    "George Gershwin",
    "Gustav Holst",
    "Adolphe Sax",
    "Kanye West",
    "Rick Rubin",
    "Metro Boomin",
    "Miles Davis",
    "Elvis Presley",
    "Herbert von Karajan",
    "David Bowie",
    "Elton John",
    "Paul McCartney",
]

INSTRUMENTS_TEST = [
    "Piccolo",
    "Viola",
    "Saxophone",
    "Violin",
    "Piano",
    "Cello",
    "Trumpet",
    "Clarinet",
    "Harp",
    "Bassoon",
]

PERFORMANCE_EVENTS_TEST = [
    "Live Aid",
    "Woodstock 1969",
    "Monterey Pop Festival",
    "Glastonbury Festival",
    "Three Tenors Concert",
    "Carnegie Hall Debut",
]

AWARDS_TEST = [
    "Grammy Awards",
    "BRIT Awards",
    "American Music Awards",
    "Billboard Music Awards",
    "MTV Video Music Awards",
    "Juno Awards",
    "Mercury Prize",
]

MUSIC_ENSEMBLES_TEST = [
    "Original Dixieland Jass Band",
    "Berlin Philharmonic",
    "Led Zeppelin",
    "Queen",
    "The Who",
    "Pink Floyd",
    "The Beatles",
    "The Rolling Stones",
    "U2",
]

MUSIC_GENRES_TEST = [
    "Jazz",
    "Classical",
    "Rock",
    "Pop",
    "Hip Hop",
    "Blues",
    "Electronic Dance Music",
]

SINGLES_TEST = [
    ("That's All Right", "Elvis Presley"),
    ("Superhero", "Metro Boomin"),
    ("Bohemian Rhapsody", "Queen"),
    ("Like a Rolling Stone", "Bob Dylan"),
    ("Thriller", "Michael Jackson"),
    ("Billie Jean", "Michael Jackson"),
    ("Hey Jude", "The Beatles"),
    ("Hotel California", "Eagles"),
    ("Respect", "Aretha Franklin"),
]

ALBUMS_TEST = [
    ("Heroes and Villains", "Metro Boomin"),
    ("Abbey Road", "The Beatles"),
    ("The Dark Side of the Moon", "Pink Floyd"),
    ("Nevermind", "Nirvana"),
    ("Back in Black", "AC/DC"),
    ("Rumours", "Fleetwood Mac"),
    ("Born to Run", "Bruce Springsteen"),
    ("Purple Rain", "Prince"),
    ("The Wall", "Pink Floyd"),
]

# --- Global Cache/State ---
# Simple cache to avoid reprocessing the exact same entity (by identifier) in one run
PROCESSED_CACHE: Dict[
    str, BaseEntity
] = {}  # Store identifier -> Pydantic model instance

# --- Helper Functions ---


def sanitize_fragment(name):
    """Clean up name for use as URI fragment or filename part."""
    # Remove special characters, replace spaces with underscores
    name = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[-\s]+", "_", name)


def create_identifier(entity_type: str, name: str, mbid: Optional[str] = None) -> str:
    """Creates a unique string identifier for an entity."""
    if mbid:
        # Use MBID for uniqueness if available
        return f"{entity_type}_{mbid}"
    else:
        # Fallback to sanitized name, less reliable for uniqueness
        return f"{entity_type}_{sanitize_fragment(name)}"


def get_mb_uri(entity_type: str, mbid: str) -> Optional[str]:
    """Creates a MusicBrainz URI string from type and MBID."""
    # Map internal types to MB URL path segments
    mb_type_map = {
        "artist": "artist",
        "release-group": "release-group",
        "release": "release",
        "recording": "recording",
        "work": "work",  # If we process works later
        "instrument": "instrument",
        "label": "label",
        "place": "place",  # MB uses 'place' for venues etc.
        "area": "area",  # MB uses 'area' for regions, countries
        "event": "event",
        "tag": "tag",  # MB uses 'tag' for genres
    }
    mb_type = mb_type_map.get(entity_type.lower())
    if mb_type:
        return f"{MB_BASE_URI}{mb_type}/{mbid}"
    else:
        print(f"Warning: Cannot generate MB URI for unknown type: {entity_type}")
        return None


def parse_mb_date(date_str: Optional[str]) -> Optional[str]:
    """Parses MusicBrainz date string (YYYY, YYYY-MM, YYYY-MM-DD) into xsd:date string (YYYY-MM-DD)."""
    if not date_str:
        return None
    try:
        if len(date_str) == 4:  # YYYY -> YYYY-01-01
            dt = datetime.strptime(date_str, "%Y")
            return f"{dt.year:04d}-01-01"
        elif len(date_str) == 7:  # YYYY-MM -> YYYY-MM-01
            dt = datetime.strptime(date_str, "%Y-%m")
            return f"{dt.year:04d}-{dt.month:02d}-01"
        elif len(date_str) == 10:  # YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.date().isoformat()  # Already YYYY-MM-DD
        else:
            # print(f"Warning: Unrecognized date format: {date_str}. Storing as string.")
            return date_str  # Keep original if format unknown
    except ValueError:
        # print(f"Warning: Could not parse date: {date_str}. Storing as string.")
        return date_str  # Keep original if parsing fails


# Modified save_entity to accept Pydantic model
def save_entity(entity_instance: BaseEntity):
    """Saves a Pydantic entity model instance to a JSON file."""
    global PROCESSED_CACHE
    if (
        not entity_instance
        or not hasattr(entity_instance, "identifier")
        or not hasattr(entity_instance, "entity_type")
    ):
        print("Warning: Cannot save entity - invalid instance provided.")
        return

    identifier = entity_instance.identifier
    entity_type = entity_instance.entity_type

    # Check cache before saving
    if identifier in PROCESSED_CACHE:
        # Optionally compare if existing data is different? For now, assume first pass is good.
        # print(f"  -> Entity {identifier} already processed/saved in this run. Skipping duplicate save.")
        return

    dir_path = os.path.join(DATA_DIR, entity_type)
    filename = f"{identifier}.json"
    filepath = os.path.join(dir_path, filename)

    try:
        os.makedirs(dir_path, exist_ok=True)
        # Dump model to dict, excluding None values and fields that weren't explicitly set
        # Use mode='json' to ensure complex types (like HttpUrl if used) are serialized correctly
        entity_dict = entity_instance.model_dump(
            mode="json", exclude_none=True, exclude_unset=True
        )

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entity_dict, f, indent=2, ensure_ascii=False)
        # print(f"  -> Saved {entity_type}: {identifier} to {filepath}")

        # Add to cache after successful save
        PROCESSED_CACHE[identifier] = entity_instance

    except ValidationError as ve:
        print(f"Error validating {entity_type} {identifier} before saving: {ve}")
    except Exception as e:
        print(f"Error saving {entity_type} {identifier} to {filepath}: {e}")


def create_and_save_time_interval(
    start_date: Optional[str],
    end_date: Optional[str],
    name: Optional[str] = None,
    source_ref: Optional[str] = None,
) -> Optional[str]:
    """Creates, validates, and saves a TimeInterval entity, returning its identifier."""
    if not start_date and not end_date:
        return None  # No interval to create

    # Create a somewhat meaningful identifier
    interval_id_part = f"{start_date or 'nodate'}_{end_date or 'nodate'}"
    if source_ref:
        interval_id_part = f"{source_ref}_{interval_id_part}"
    identifier = create_identifier("TimeInterval", interval_id_part)

    data_dict = {
        "identifier": identifier,
        "entity_type": "TimeInterval",
        "hasStartTime": start_date,
        "hasEndTime": end_date,                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
        "hasName": name
        or f"Interval: {start_date or '?'} to {end_date or '?'}",  # Basic name
    }

    try:
        interval_instance = TimeInterval(**data_dict)
        save_entity(interval_instance)
        return interval_instance.identifier
    except ValidationError as ve:
        print(f"Error validating TimeInterval ({identifier}): {ve}")
        return None


def process_place(place_data: Dict[str, Any]) -> Optional[str]:
    """Processes Place data from MB, saves Place JSON, returns identifier."""
    if not place_data or not place_data.get("name"):
        return None

    place_name = place_data["name"]
    place_mbid = place_data.get("id")
    identifier = create_identifier("Place", place_name, place_mbid)

    # Check if already processed
    if identifier in PROCESSED_CACHE:
        return identifier
    
    address = place_data.get("address")
    coordinates = place_data.get("coordinates")
    place_type = place_data.get("type")

    # Combine into single string:
    if address:
        address_str = f"Address:{address}"
    else:
        address_str = ""
    if coordinates:
        coordinates_str = f"Coords:{coordinates.get('latitude')},{coordinates.get('longitude')}"
    else:
        coordinates_str = ""
    if place_type:
        place_type_str = f"Type:{place_type}"
    else:
        place_type_str = ""

    combined_str = f"{place_name} | {address_str} | {coordinates_str} | {place_type_str}"

    data_dict = {
        "identifier": identifier,
        "entity_type": "Place",  # Model: Place
        "hasName": place_name,
        "hasDescription": combined_str.strip(),  # Combined description
        # Removed: "mbid": place_mbid,
        # Removed: "sameAs": [mb_uri] if mb_uri else None,
        # Removed: "description": place_data.get('disambiguation')
    }

    try:
        place_instance = Place(**data_dict)
        save_entity(place_instance)
        return place_instance.identifier
    except ValidationError as ve:
        print(f"Error validating Place ({identifier}): {ve}")
        return None


def process_country(
    country_code: str, country_name: Optional[str] = None
) -> Optional[str]:
    """Processes Country data, saves JSON, returns identifier."""
    if not country_code:
        return None

    # Use code for name if name not provided, and for identifier consistency
    name = country_name or country_code
    identifier = create_identifier("Country", name)  # Use name (code) for identifier

    # Check if already processed
    if identifier in PROCESSED_CACHE:
        return identifier

    # Fetch MBID for country (area)? Not strictly needed for JSON, adds API calls. Skip for now.
    # mb_uri = get_mb_uri('area', mbid) # If we fetched MBID

    data_dict = {
        "identifier": identifier,
        "entity_type": "Country",  # Model: Country
        "hasName": name,
        "hasDescription": f"Country code: {country_code} | Country name: {name}",
        # Removed: "sameAs": [mb_uri] if mb_uri else None
    }

    try:
        country_instance = Country(**data_dict)
        save_entity(country_instance)
        return country_instance.identifier
    except ValidationError as ve:
        print(f"Error validating Country ({identifier}): {ve}")
        return None


def process_label(label_data: Dict[str, Any]) -> Optional[str]:
    """Processes Record Label data from MB, saves JSON, returns identifier."""
    if not label_data or not label_data.get("name"):
        return None

    label_name = label_data["name"]
    label_mbid = label_data.get("id")
    identifier = create_identifier("RecordLabel", label_name, label_mbid)

    # Check if already processed
    if identifier in PROCESSED_CACHE:
        return identifier

    # Removed: mb_uri = get_mb_uri('label', label_mbid) if label_mbid else None

    data_dict = {
        "identifier": identifier,
        "entity_type": "RecordLabel",  # Model: RecordLabel
        "name": label_name,
        # Removed: "mbid": label_mbid,
        # Removed: "sameAs": [mb_uri] if mb_uri else None,
        "hasDescription": f"Label type: {label_data.get('type')} | Label name: {label_name}",
        # Removed: "description": label_data.get('disambiguation')
    }

    try:
        label_instance = RecordLabel(**data_dict)
        save_entity(label_instance)
        return label_instance.identifier
    except ValidationError as ve:
        print(f"Error validating RecordLabel ({identifier}): {ve}")
        return None


# --- Processing Functions (Refactored with Pydantic) ---


def process_artist(
    client: MusicBrainzClient, name: str, is_ensemble: bool
) -> Optional[str]:
    """
    Searches for an artist/ensemble, fetches details, builds Pydantic model,
    saves related entities (Place, Country, Genre, Membership, TimeInterval),
    and saves the main artist/ensemble JSON. Returns the identifier.
    """
    global PROCESSED_CACHE
    print(f"Processing Artist/Ensemble: {name}...")
    search_func = client.search_ensemble if is_ensemble else client.search_artist
    mb_entity_type = "artist"  # MusicBrainz uses 'artist' for both persons and groups
    hom_entity_type = "MusicEnsemble" if is_ensemble else "Musician"
    model_class = MusicEnsemble if is_ensemble else Musician

    # --- Initial Search ---
    search_results = search_func(name, limit=1)
    time.sleep(0.1)  # Small delay

    if not search_results or not search_results.get(mb_entity_type + "s"):
        print(f"  -> Could not find {name} on MusicBrainz.")
        return None

    entity_data_mb = search_results[mb_entity_type + "s"][0]
    mbid = entity_data_mb.get("id")
    mb_name = entity_data_mb.get("name")
    if not mbid:
        print(f"  -> Found {mb_name} but no MBID. Cannot reliably process.")
        return None

    identifier = create_identifier(hom_entity_type, mb_name, mbid)
    # Removed: mb_uri = get_mb_uri(mb_entity_type, mbid)

    # --- Check Cache ---
    if identifier in PROCESSED_CACHE:
        print(
            f"  -> Already processed {hom_entity_type} {mb_name} ({identifier}). Skipping."
        )
        return identifier

    print(f"  -> Found MBID: {mbid} for {mb_name}")

    # --- Basic Data Dictionary ---
    data_dict: Dict[str, Any] = {
        "identifier": identifier,
        "entity_type": hom_entity_type,  # Model: Musician or MusicEnsemble
        "hasName": mb_name,
        "sort_name": entity_data_mb.get("sort-name"),
        # Removed: "mbid": mbid,
        # Removed: "sameAs": [mb_uri] if mb_uri else [],
        # Removed: "sort_name": entity_data_mb.get("sort-name"),
        # Removed: "disambiguation": entity_data_mb.get("disambiguation"),
        "hasDescription": entity_data_mb.get(
            "disambiguation"
        ),  # Check if Musician/Ensemble model has this field? Assume yes for now.
    }
    if data_dict["sort_name"] == data_dict["hasName"]:  # Avoid redundant sort name
        data_dict["sort_name"] = None

    # --- Fetch Detailed Info ---
    # Request relations, tags, area, urls etc.
    inc_params = ["artist-rels", "tags", "area-rels", "place-rels", "url-rels"]
    details = client.lookup_artist(mbid, inc=inc_params)
    time.sleep(0.1)

    if not details:
        print(
            f"  -> Could not fetch details for {mb_name} ({mbid}). Saving basic info."
        )
        # Try to create and save with basic info
        try:
            instance = model_class(**data_dict)
            save_entity(instance)
            return instance.identifier
        except ValidationError as ve:
            print(f"  -> Error validating basic {hom_entity_type} ({identifier}): {ve}")
            return None

    # --- Process Details ---

    # Description - removed from BaseEntity, check if specific models have it
    # data_dict["description"] = details.get('disambiguation')

    # Life Span / Formation/Dissolution -> TimeInterval
    life_span = details.get("life-span")
    if life_span:
        begin_date_str = life_span.get("begin")
        end_date_str = life_span.get("end")
        begin_date = parse_mb_date(begin_date_str)
        end_date = parse_mb_date(end_date_str)

        interval_name = (
            f"Lifespan of {mb_name}"
            if not is_ensemble
            else f"Activity period of {mb_name}"
        )
        time_interval_id = create_and_save_time_interval(
            begin_date, end_date, interval_name, identifier
        )
        if time_interval_id:
            # Check if model has hasTimeInterval field
            if hasattr(model_class, "hasTimeInterval"):
                data_dict["hasTimeInterval"] = time_interval_id  # Link to the interval

        # Store specific dates directly on model too, as per mappings
        if is_ensemble:
            if begin_date:
                data_dict["formationDate"] = begin_date
            if end_date:
                data_dict["dissolutionDate"] = end_date
        else:
            if begin_date:
                data_dict["hasBirthDate"] = begin_date
            if end_date:
                data_dict["hasDeathDate"] = end_date

    # Gender (for Musicians)
    if not is_ensemble:
        data_dict["gender"] = details.get("gender")
        # Extract first/last name? MB doesn't provide separate fields reliably.
        # Name parsing is complex, skip for now. Keep full name in 'name'.

    # Country / Area / Place
    # Mappings: Musician -> hasBirthPlace (Place), livesIn (Place)
    # Mappings: MusicEnsemble -> wasFormedIn (Place)

    begin_area_mb = details.get("begin_area")  # MB Area object for birth/formation

    birth_formation_place_id = None
    if begin_area_mb:
        # Process this as a Place, regardless of its MB type (Area/Place)
        birth_formation_place_id = process_place(begin_area_mb)
        if birth_formation_place_id:
            if is_ensemble:
                data_dict["wasFormedIn"] = birth_formation_place_id
            else:
                data_dict["hasBirthPlace"] = birth_formation_place_id

    # Try to find a 'residence' place from relations (for 'livesIn')
    # Try to link country_code to a Country entity

    # Genres (Tags) -> hasGenre
    tags = details.get("tags", [])
    if tags:
        genre_identifiers = []
        tags.sort(key=lambda x: x.get("count", 0), reverse=True)
        for tag in tags[:5]:  # Top 5 tags
            genre_name_tag = tag.get("name")
            # MB tags sometimes have IDs which are UUIDs, not genre MBIDs. Search by name.
            # genre_mbid_tag = tag.get('id') # This ID might not be useful
            if genre_name_tag:
                genre_id = process_genre(
                    client, genre_name_tag
                )  # Find/create genre by name
                if genre_id:
                    genre_identifiers.append(genre_id)

        if genre_identifiers and hasattr(model_class, "hasGenre"):
            data_dict["hasGenre"] = list(set(genre_identifiers))  # Ensure unique

    # Relationships (Members, Labels etc.)
    relations = details.get("relations", [])
    membership_identifiers = []

    for rel in relations:
        rel_type = rel.get("type")
        direction = rel.get("direction", "forward")

        # --- Ensemble Membership (Processing members if current entity is ensemble) ---
        if is_ensemble and rel_type == "member of band" and direction == "backward":
            target_entity = rel.get("artist")
            if not target_entity:
                continue
            member_mbid = target_entity.get("id")
            member_name = target_entity.get("name")
            if not member_mbid or not member_name:
                continue

            # Process the member artist (recursion, ensure cache check works)
            # Assume members are Musicians (is_ensemble=False)
            member_identifier = process_artist(client, member_name, is_ensemble=False)
            if not member_identifier:
                print(f"    -> Could not process member: {member_name}")
                continue

            # Create TimeInterval for membership duration
            mem_start = parse_mb_date(rel.get("begin"))
            mem_end = parse_mb_date(rel.get("end"))
            mem_interval_name = f"Membership of {member_name} in {mb_name}"
            mem_interval_id = create_and_save_time_interval(
                mem_start,
                mem_end,
                mem_interval_name,
                f"{identifier}_{member_identifier}",
            )

            # Create Membership Entity
            membership_id = create_identifier(
                "MusicEnsembleMembership", f"{member_mbid}_{mbid}"
            )
            membership_data = {
                "identifier": membership_id,
                "entity_type": "MusicEnsembleMembership",  # Model: MusicEnsembleMembership
                "hasName": f"Membership: {member_name} in {mb_name}",
                "involvesMemberOfMusicEnsemble": member_identifier,
                "involvesMusicEnsemble": identifier,
                "hasTimeInterval": mem_interval_id,
                # Removed: "description": role ?
            }
            try:
                membership_instance = MusicEnsembleMembership(**membership_data)
                save_entity(membership_instance)
                membership_identifiers.append(membership_id)
            except ValidationError as ve:
                print(f"    -> Error validating Membership ({membership_id}): {ve}")

        # --- Label Signing (for Musicians/Ensembles) ---
        # MB doesn't have a direct "signed to" relation AFAIK. This comes from release label info.
        # We'll add labels during release processing.

    if is_ensemble and membership_identifiers and hasattr(model_class, "memberships"):
        data_dict["memberships"] = list(set(membership_identifiers))

    # Add URLs - removed from BaseEntity
    # url_rels = details.get('url-rels', [])
    # urls: Dict[str, List[str]] = {}
    # for url_rel in url_rels:
    #     rel_type_url = url_rel.get('type')
    #     target_url = url_rel.get('url', {}).get('resource')
    #     if rel_type_url and target_url:
    #         if rel_type_url not in urls: urls[rel_type_url] = []
    #         if target_url not in urls[rel_type_url]: urls[rel_type_url].append(target_url)
    # if urls:
    #     data_dict["urls"] = urls

    # --- Final Validation and Save ---
    try:
        instance = model_class(**data_dict)
        save_entity(instance)
        print(f"  -> Finished processing {mb_name} ({identifier})")
        return instance.identifier
    except ValidationError as ve:
        print(f"  -> Error validating final {hom_entity_type} ({identifier}): {ve}")
        # Optionally save raw data or partial data? For now, just report error.
        # Save the raw 'details' dict?
        # error_dir = os.path.join(DATA_DIR, "_errors")
        # os.makedirs(error_dir, exist_ok=True)
        # error_filepath = os.path.join(error_dir, f"{identifier}_error.json")
        # with open(error_filepath, 'w', encoding='utf-8') as f:
        #     json.dump(details, f, indent=2, ensure_ascii=False)
        return None


def process_instrument(client: MusicBrainzClient, name: str) -> Optional[str]:
    """Searches for instrument, fetches details, builds Pydantic model, saves JSON, returns identifier."""
    global PROCESSED_CACHE
    print(f"Processing Instrument: {name}...")
    hom_entity_type = "Instrument"
    model_class = Instrument

    # Check cache based on name first (MBID lookup needed)
    # temp_identifier = create_identifier(hom_entity_type, name)
    # if temp_identifier in PROCESSED_CACHE: return temp_identifier # Risky if name collision

    search_results = client.search_instrument(name, limit=1)
    time.sleep(0.1)

    if not search_results or not search_results.get("instruments"):
        print(f"  -> Could not find {name} on MusicBrainz.")
        return None

    instr_data_mb = search_results["instruments"][0]
    mbid = instr_data_mb.get("id")
    mb_name = instr_data_mb.get("name")
    if not mbid:
        print(f"  -> Found {mb_name} but no MBID.")
        return None  # Need MBID for reliable processing

    identifier = create_identifier(hom_entity_type, mb_name, mbid)
    # Removed: mb_uri = get_mb_uri('instrument', mbid)

    # Check cache with proper identifier
    if identifier in PROCESSED_CACHE:
        print(
            f"  -> Already processed {hom_entity_type} {mb_name} ({identifier}). Skipping."
        )
        return identifier

    print(f"  -> Found MBID: {mbid} for {mb_name}")

    data_dict: Dict[str, Any] = {
        "identifier": identifier,
        "entity_type": hom_entity_type,  # Model: Instrument
        "hasName": mb_name,
        # Removed: "mbid": mbid,
        # Removed: "sameAs": [mb_uri] if mb_uri else [],
        # Removed: "source_search_term": name
    }

    # Fetch details
    # Include 'artist-rels' for inventor? Yes, mapping: wasInventedBy (Agent)
    details = client.lookup_instrument(mbid, inc=["tags", "artist-rels", "url-rels"])
    time.sleep(0.1)

    if not details:
        print(
            f"  -> Could not fetch details for {mb_name} ({mbid}). Saving basic info."
        )
        try:
            instance = model_class(**data_dict)
            save_entity(instance)
            return instance.identifier
        except ValidationError as ve:
            print(f"  -> Error validating basic {hom_entity_type} ({identifier}): {ve}")
            return None

    # Process details
    # Removed: data_dict["description"] = details.get('description') or details.get('disambiguation')
    data_dict["instrument_type"] = details.get("type")

    instrument_description = details.get("description") or details.get("disambiguation")
    data_dict["hasDescription"] = f"Instrument name: {mb_name} | Type: {data_dict['instrument_type']} | Additional info: {instrument_description}"

    # Invention Info -> wasInventedBy (list of Musician identifiers), inventionDate
    relations = details.get("relations", [])
    inventor_identifiers = []
    invention_dates = []
    for rel in relations:
        rel_type = rel.get("type")
        # Mappings: wasInventedBy (Agent) -> Process artist as Musician
        if rel_type == "inventor":
            inventor_entity = rel.get("artist")
            if inventor_entity:
                inventor_name = inventor_entity.get("name")
                inventor_mbid = inventor_entity.get("id")
                if inventor_name and inventor_mbid:
                    # Process inventor artist (assume Musician)
                    inventor_id = process_artist(
                        client, inventor_name, is_ensemble=False
                    )
                    if inventor_id:
                        inventor_identifiers.append(inventor_id)

            # Mappings: wasInventedAtTime (TimeInterval) -> Store as inventionDate for simplicity
            invention_date_str = rel.get("begin")  # MB uses 'begin'
            invention_date = parse_mb_date(invention_date_str)
            if invention_date and invention_date not in invention_dates:
                invention_dates.append(invention_date)

    if inventor_identifiers and hasattr(model_class, "wasInventedBy"):
        data_dict["wasInventedBy"] = list(set(inventor_identifiers))
    if invention_dates and hasattr(model_class, "inventionDate"):
        data_dict["inventionDate"] = min(invention_dates)

    # Add URLs - removed
    # url_rels = details.get('url-rels', [])
    # urls: Dict[str, List[str]] = {}
    # for url_rel in url_rels:
    #     rel_type_url = url_rel.get('type')
    #     target_url = url_rel.get('url', {}).get('resource')
    #     if rel_type_url and target_url:
    #         if rel_type_url not in urls: urls[rel_type_url] = []
    #         if target_url not in urls[rel_type_url]: urls[rel_type_url].append(target_url)
    # if urls: data_dict["urls"] = urls

    # Add Tags - removed
    # tags = details.get('tags', [])
    # if tags: data_dict["tags_raw"] = tags[:5]

    # --- Final Validation and Save ---
    try:
        instance = model_class(**data_dict)
        save_entity(instance)
        print(f"  -> Finished processing {mb_name} ({identifier})")
        return instance.identifier
    except ValidationError as ve:
        print(f"  -> Error validating final {hom_entity_type} ({identifier}): {ve}")
        return None


def process_genre(client: MusicBrainzClient, name: str) -> Optional[str]:
    """Creates or finds genre entity, saves JSON using Pydantic model. Searches MB tag."""
    global PROCESSED_CACHE
    print(f"Processing Genre: {name}...")
    hom_entity_type = "MusicGenre"
    model_class = MusicGenre

    # --- Check Cache/Existing File ---
    # Need MBID for reliable ID. Search MB first.
    mbid_found = None

    print(f"  -> Searching MusicBrainz tag: {name}...")
    search_results = client.search_genre(name, limit=1)  # Search MB 'tag' endpoint
    time.sleep(0.1)

    if search_results and search_results.get("tags"):
        tag_data = search_results["tags"][0]
        # Basic name match check (case-insensitive)
        if tag_data.get("name", "").lower() == name.lower():
            mbid_found = tag_data.get("id")  # This is the tag UUID
            mb_name_found = tag_data.get("name")
            if mbid_found:
                print(f"  -> Found MB tag: {mb_name_found} (ID: {mbid_found})")
        else:
            print(
                f"  -> Found tag '{tag_data.get('name')}', but name mismatch. Treating as non-MB genre."
            )
    else:
        print("  -> No matching tag found on MusicBrainz.")

    # --- Create Identifier & Check Cache ---
    # Use name for identifier if no MBID found
    identifier = create_identifier(hom_entity_type, name, mbid_found)

    if identifier in PROCESSED_CACHE:
        print(
            f"  -> Already processed {hom_entity_type} {name} ({identifier}). Skipping."
        )
        return identifier

    # --- Prepare Data ---
    data_dict: Dict[str, Any] = {
        "identifier": identifier,
        "entity_type": hom_entity_type,  # Model: MusicGenre
        "hasName": name,
        # Removed: "mbid": mbid_found,
        # Removed: "sameAs": [mb_uri] if mb_uri else [],
        # Removed: "source_search_term": name
    }
    # Removed description mapping
    # if mb_name_found and mb_name_found != name:
    #     data_dict["description"] = f"MusicBrainz Tag Name: {mb_name_found}"

    # --- Validate and Save ---
    try:
        instance = model_class(**data_dict)
        save_entity(instance)
        print(f"  -> Finished processing Genre: {name} ({identifier})")
        return instance.identifier
    except ValidationError as ve:
        print(f"  -> Error validating {hom_entity_type} ({identifier}): {ve}")
        return None


def process_recording(
    client: MusicBrainzClient,
    recording_data_mb: Dict[str, Any],
    release_identifier: str,
) -> Optional[str]:
    """Processes Recording data from MB, saves JSON using Pydantic model, returns identifier."""
    global PROCESSED_CACHE
    hom_entity_type = "Recording"
    model_class = Recording

    mbid = recording_data_mb.get("id")
    mb_title = recording_data_mb.get("title")

    if not mbid or not mb_title:
        print("  -> Skipping recording: missing MBID or title.")
        return None

    identifier = create_identifier(hom_entity_type, mb_title, mbid)
    # Removed: mb_uri = get_mb_uri('recording', mbid)

    # Check cache
    if identifier in PROCESSED_CACHE:
        # print(f"    -> Already processed Recording {mb_title} ({identifier}). Skipping.")
        return identifier

    print(f"    -> Processing Recording: {mb_title} ({mbid})")

    data_dict: Dict[str, Any] = {
        "identifier": identifier,
        "entity_type": hom_entity_type,  # Model: Recording
        "hasTitle": mb_title,
        "hasName": mb_title,
        # Removed: "mbid": mbid,
        # Removed: "sameAs": [mb_uri] if mb_uri else [],
        "isPartOfRelease": release_identifier,
        # Removed: "description": recording_data_mb.get('disambiguation'),
        "duration": recording_data_mb.get("length"),
    }

    # Optional: Process artist credits for the recording?
    artist_credit = recording_data_mb.get("artist-credit", [])
    recording_artist_ids = []
    if artist_credit:
        for credit in artist_credit:
            artist_info = credit.get("artist")
            if artist_info:
                artist_name_rec = artist_info.get("name")
                artist_mbid_rec = artist_info.get("id")
                if artist_name_rec and artist_mbid_rec:
                    print(
                        f"      -> Processing artist credit: {artist_name_rec} ({artist_mbid_rec})"
                    )
                    artist_details_rec = client.lookup_artist(
                        artist_mbid_rec, inc=[]
                    )  # No inc needed, just type
                    time.sleep(0.1)  # Rate limit
                    artist_type_rec = (
                        artist_details_rec.get("type") if artist_details_rec else None
                    )
                    if artist_type_rec:
                        is_ensemble_rec = artist_type_rec == "Group"
                        artist_id_rec = process_artist(
                            client, artist_name_rec, is_ensemble=is_ensemble_rec
                        )
                        if artist_id_rec:
                            recording_artist_ids.append(artist_id_rec)
                        else:
                            print(
                                f"      -> Failed to process artist {artist_name_rec} for recording {mb_title}"
                            )
                    else:
                        print(
                            f"      -> Could not determine type for artist {artist_name_rec} ({artist_mbid_rec}). Skipping credit link."
                        )

    if recording_artist_ids and hasattr(model_class, "hasArtist"):
        data_dict["hasArtist"] = list(
            set(recording_artist_ids)
        )  # Add the list of artist identifiers

    # Optional: Link to Work? Requires inc=works and work processing logic
    # work_rels = recording_data_mb.get('work-rels', [])

    # --- Validate and Save ---
    try:
        instance = model_class(**data_dict)
        save_entity(instance)
        # print(f"    -> Finished Recording: {mb_title} ({identifier})")
        return instance.identifier
    except ValidationError as ve:
        print(f"    -> Error validating {hom_entity_type} ({identifier}): {ve}")
        return None


def process_release(
    client: MusicBrainzClient, title: str, artist_name: str, release_type: str
) -> Optional[str]:
    """
    Searches for a release (album/single), fetches details (incl. recordings),
    builds Pydantic model, saves related (Artist, Genre, Recording, Country, Label),
    saves JSON, returns identifier.
    """
    global PROCESSED_CACHE
    print(f"\nProcessing {release_type.capitalize()}: {title} by {artist_name}...")
    hom_entity_type = release_type.capitalize()  # Album or Single
    if hom_entity_type not in MODEL_MAP:
        print(f"  -> Error: Unknown release type '{release_type}'. Skipping.")
        return None
    model_class = MODEL_MAP[hom_entity_type]

    # --- Search Release Group ---
    # Search MB release-group endpoint
    search_results = client.search_release_group(
        title, artist_name=artist_name, limit=1, type=release_type
    )
    time.sleep(0.1)

    if not search_results or not search_results.get("release-groups"):
        print(
            f"  -> Could not find Release Group for {title} by {artist_name} on MusicBrainz."
        )
        return None

    rg_data = search_results["release-groups"][0]
    rg_mbid = rg_data.get("id")  # Release Group MBID
    rg_title = rg_data.get("title")
    primary_type_mb = rg_data.get("primary-type")  # Album, Single, EP etc. from MB

    if not rg_mbid:
        print(f"  -> Found {rg_title} but no Release Group MBID.")
        return None

    identifier = create_identifier(hom_entity_type, rg_title, rg_mbid)
    # Removed: rg_mb_uri = get_mb_uri('release-group', rg_mbid)

    # --- Check Cache ---
    if identifier in PROCESSED_CACHE:
        print(
            f"  -> Already processed {hom_entity_type} {rg_title} ({identifier}). Skipping."
        )
        return identifier

    print(
        f"  -> Found Release Group MBID: {rg_mbid} for {rg_title} (Type: {primary_type_mb})"
    )

    # --- Basic Data Dictionary ---
    data_dict: Dict[str, Any] = {
        "identifier": identifier,
        "entity_type": hom_entity_type,  # Model: Album or Single
        "hasTitle": rg_title,
        "hasName": rg_title,
        # Removed: "mbid_rg": rg_mbid,
        # Removed: "sameAs": [rg_mb_uri] if rg_mb_uri else [],
        # Removed: "mb_primary_type": primary_type_mb,
        # Removed: "source_search_term": f"{title} by {artist_name}",
        # Removed: "description": rg_data.get('disambiguation')
    }

    # --- Process Primary Artist ---
    artist_credit = rg_data.get("artist-credit", [])
    primary_artist_id = None
    if artist_credit:
        primary_artist_mb_info = artist_credit[0].get("artist")
        if primary_artist_mb_info:
            artist_name_mb = primary_artist_mb_info.get("name", artist_name)
            artist_type_mb = primary_artist_mb_info.get("type")  # Person / Group
            is_ensemble_artist = artist_type_mb == "Group"
            # Process the primary artist using MB data
            primary_artist_id = process_artist(
                client, artist_name_mb, is_ensemble=is_ensemble_artist
            )
    else:
        # Fallback: try processing using the input artist_name (requires guessing type)
        print(
            f"  -> Warning: No detailed artist credit found. Attempting process with input name '{artist_name}'."
        )
        # Guess type based on initial lists (less reliable)
        is_ensemble_guess = artist_name in MUSIC_ENSEMBLES_TEST
        primary_artist_id = process_artist(
            client, artist_name, is_ensemble=is_ensemble_guess
        )

    if primary_artist_id:
        data_dict["hasArtist"] = primary_artist_id
    else:
        print(
            f"  -> Warning: Could not process artist '{artist_name}' for release {rg_title}. Release JSON will lack artist link."
        )

    # --- First Release Date ---
    first_release_date_str = rg_data.get("first-release-date")
    if hasattr(model_class, "releaseDate"):
        data_dict["releaseDate"] = parse_mb_date(first_release_date_str)

    # --- Fetch Details (incl. Releases, Tags, Artist) ---
    # WORKAROUND: Fetch releases first, then recordings per release, due to 400 errors with inc=recordings on RG lookup
    inc_params = [
        "releases",
        "artists",
        "tags",
    ]  # Include releases, artist credits, tags for the group

    details = client.lookup_release_group(rg_mbid, inc=inc_params)
    time.sleep(0.1)

    if not details:
        print(
            f"  -> Could not fetch release group details for {rg_title} ({rg_mbid}). Saving basic info."
        )
        try:
            instance = model_class(**data_dict)
            save_entity(instance)
            return instance.identifier
        except ValidationError as ve:
            print(f"  -> Error validating basic {hom_entity_type} ({identifier}): {ve}")
            return None

    # --- Process Details from Release Group --- (Genres, potentially artist credit if needed)
    # Primary artist should already be handled from initial search data, but check details artist credit if needed
    # ... (primary artist processing code might need refinement based on what 'details' contains now)

    # Genres from release group tags -> hasGenre
    tags = details.get("tags", [])
    if tags:
        genre_identifiers = []
        tags.sort(key=lambda x: x.get("count", 0), reverse=True)
        for tag in tags[:5]:  # Top 5
            genre_name_tag = tag.get("name")
            if genre_name_tag:
                genre_id = process_genre(client, genre_name_tag)
                if genre_id:
                    genre_identifiers.append(genre_id)
        if genre_identifiers and hasattr(model_class, "hasGenre"):
            data_dict["hasGenre"] = list(set(genre_identifiers))

    # --- Process Specific Releases for Details and Recordings (WORKAROUND) ---
    releases_mb = details.get(
        "releases", []
    )  # Get list of specific releases in the group
    release_specifics_list = []
    processed_release_mbids_for_details = set()  # Avoid redundant detail processing
    processed_recording_mbids = (
        set()
    )  # Avoid duplicate recording processing across releases
    all_label_ids_on_release = set()
    recording_identifiers = []  # Store IDs of recordings processed for this release group

    if releases_mb:
        print(
            f"  -> Found {len(releases_mb)} specific releases. Querying each for recordings & details (up to 5)... "
        )

        for release_specific_mb in releases_mb[:5]:  # Limit API calls
            release_mbid_spec = release_specific_mb.get("id")
            if (
                not release_mbid_spec
                or release_mbid_spec in processed_release_mbids_for_details
            ):
                continue
            processed_release_mbids_for_details.add(release_mbid_spec)

            # --- 1. Process this specific release for details (country, label, format) ---
            # (This part is similar to before, extracting info for the 'release_specifics' list)
            release_spec_uri = get_mb_uri("release", release_mbid_spec)
            spec_data: Dict[str, Any] = {
                "release_mbid": release_mbid_spec,
                "release_mb_uri": release_spec_uri,
                "hasTitle": release_specific_mb.get("title", rg_title),
                "status": release_specific_mb.get("status"),
                "date": parse_mb_date(release_specific_mb.get("date")),
            }
            # ... (Country, Label, Format processing logic remains the same as before, using release_specific_mb) ...
            # Release Country
            country_code_rel = release_specific_mb.get("country")
            if country_code_rel:
                country_id_rel = process_country(country_code_rel)
                if country_id_rel:
                    spec_data["wasReleasedIn"] = country_id_rel
            # Record Label
            label_info_list = release_specific_mb.get("label-info", [])
            labels_on_this_specific_release = []
            for lbl_info in label_info_list:
                label_detail = lbl_info.get("label")
                if label_detail:
                    label_id = process_label(label_detail)
                    if label_id:
                        labels_on_this_specific_release.append(
                            {
                                "label_id": label_id,
                                "catalog_number": lbl_info.get("catalog-number"),
                            }
                        )
                        all_label_ids_on_release.add(label_id)
            if labels_on_this_specific_release:
                spec_data["hasLabel"] = labels_on_this_specific_release
            # Media/Format info
            media_list = release_specific_mb.get("media", [])
            formats = set()
            track_count = 0
            for medium in media_list:
                fmt = medium.get("format")
                if fmt:
                    formats.add(fmt)
                track_count += medium.get("track-count", 0)
            if formats:
                spec_data["formats"] = sorted(list(formats))
            if track_count:
                spec_data["track_count"] = track_count

            release_specifics_list.append(spec_data)

            # --- 2. Fetch recordings for THIS specific release ---
            print(f"    -> Fetching recordings for release: {release_mbid_spec}...")
            try:
                release_details = client.lookup_release(
                    release_mbid_spec, inc=["recordings", "artist-credits"]
                )  # Include necessary fields
                time.sleep(0.1)
                if release_details:
                    recordings_list_spec = release_details.get("media", [])
                    if recordings_list_spec:
                        for medium in recordings_list_spec:
                            tracks = medium.get("tracks", [])
                            for track in tracks:
                                recording_data = track.get("recording")
                                if recording_data:
                                    recording_mbid = recording_data.get("id")
                                    # Avoid processing same recording multiple times
                                    if (
                                        recording_mbid
                                        and recording_mbid
                                        not in processed_recording_mbids
                                    ):
                                        processed_recording_mbids.add(recording_mbid)
                                        # Process the recording, linking it back to the main RELEASE GROUP identifier
                                        rec_id = process_recording(
                                            client, recording_data, identifier
                                        )
                                        if rec_id:
                                            recording_identifiers.append(rec_id)
            except Exception as e:
                print(
                    f"    -> Error fetching/processing recordings for release {release_mbid_spec}: {e}"
                )

    # Add the collected release specifics list (if any) to the main data dict
    if release_specifics_list and hasattr(model_class, "release_specifics"):
        data_dict["release_specifics"] = release_specifics_list

    # Recordings were processed individually and saved with a link back. No need to store IDs here.
    print(
        f"  -> Found and processed {len(recording_identifiers)} unique recordings for this release group."
    )

    # Add URLs - removed from BaseEntity
    # url_rels = details.get('url-rels', []) # URLs might be on release group level
    # ... (URL processing logic removed) ...
    # if urls: data_dict["urls"] = urls

    # --- Final Validation and Save ---
    try:
        instance = model_class(**data_dict)
        save_entity(instance)
        print(f"  -> Finished processing {hom_entity_type}: {rg_title} ({identifier})")
        return instance.identifier
    except ValidationError as ve:
        print(f"  -> Error validating final {hom_entity_type} ({identifier}): {ve}")
        return None


def process_event(client: MusicBrainzClient, name: str) -> Optional[str]:
    """Searches for performance event, fetches details, builds Pydantic model, saves JSON, returns identifier."""
    global PROCESSED_CACHE
    print(f"Processing Event: {name}...")
    hom_entity_type = "PerformanceEvent"
    model_class = PerformanceEvent

    search_results = client.search_event(name, limit=1)
    time.sleep(0.1)

    if not search_results or not search_results.get("events"):
        print(f"  -> Could not find event {name} on MusicBrainz.")
        return None

    event_data_mb = search_results["events"][0]
    mbid = event_data_mb.get("id")
    mb_name = event_data_mb.get("name")
    event_type_mb = event_data_mb.get("type")  # Concert, Festival etc.

    if not mbid:
        print(f"  -> Found {mb_name} but no MBID.")
        return None

    identifier = create_identifier(hom_entity_type, mb_name, mbid)
    # Removed: mb_uri = get_mb_uri('event', mbid)

    # Check cache
    if identifier in PROCESSED_CACHE:
        print(
            f"  -> Already processed {hom_entity_type} {mb_name} ({identifier}). Skipping."
        )
        return identifier

    print(f"  -> Found Event MBID: {mbid} for {mb_name} (Type: {event_type_mb})")

    data_dict: Dict[str, Any] = {
        "identifier": identifier,
        "entity_type": hom_entity_type,  # Model: PerformanceEvent
        "hasName": mb_name,
        # Removed: "mbid": mbid,
        # Removed: "sameAs": [mb_uri] if mb_uri else [],
        # Removed: "mb_type": event_type_mb,
        # Removed: "source_search_term": name,
        # Removed: "description": event_data_mb.get('disambiguation')
    }

    # Fetch details
    details = client.lookup_event(mbid, inc=["place-rels", "artist-rels", "url-rels"])
    time.sleep(0.1)

    if not details:
        print(
            f"  -> Could not fetch details for {mb_name} ({mbid}). Saving basic info."
        )
        try:
            instance = model_class(**data_dict)
            save_entity(instance)
            return instance.identifier
        except ValidationError as ve:
            print(f"  -> Error validating basic {hom_entity_type} ({identifier}): {ve}")
            return None

    # Process details

    # Time Interval -> hasTimeInterval
    life_span = details.get("life-span")
    if life_span:
        begin_date_str = life_span.get("begin")
        end_date_str = life_span.get("end")
        begin_date = parse_mb_date(begin_date_str)
        end_date = parse_mb_date(end_date_str)
        interval_name = f"Time of {mb_name}"
        time_interval_id = create_and_save_time_interval(
            begin_date, end_date, interval_name, identifier
        )
        if time_interval_id:
            data_dict["hasTimeInterval"] = time_interval_id
        data_dict["cancelled"] = life_span.get(
            "cancelled", False
        )  # Store cancelled status

    # Relations: Place -> eventLocation, Artists -> performedBy
    relations = details.get("relations", [])
    place_identifier = None
    agent_identifiers = []

    for rel in relations:
        rel_type = rel.get("type")

        # --- Held At (Place) -> eventLocation ---
        if rel_type == "held at":
            place_entity = rel.get("place")
            if place_entity and not place_identifier:  # Take the first place found
                place_id = process_place(place_entity)
                if place_id:
                    place_identifier = place_id

        # --- Performer (Artist) -> involvesAgent ---
        # Map various performer/artist relations to involvesAgent
        elif (
            rel_type == "performer" or rel_type == "main performer"
        ):  # Add other relevant types if needed
            artist_entity = rel.get("artist")
            if artist_entity:
                artist_name = artist_entity.get("name")
                artist_mbid = artist_entity.get("id")
                artist_type_mb = artist_entity.get("type")  # Person / Group
                if artist_name and artist_mbid:
                    is_ensemble = artist_type_mb == "Group"
                    # Process the artist (musician/ensemble)
                    artist_id = process_artist(
                        client, artist_name, is_ensemble=is_ensemble
                    )
                    if artist_id:
                        agent_identifiers.append(artist_id)
                    else:
                        print(
                            f"    -> Failed to process performer/agent {artist_name} (MBID: {artist_mbid}) for event {mb_name}."
                        )

    if place_identifier:
        data_dict["eventLocation"] = place_identifier
    if agent_identifiers:
        data_dict["involvesAgent"] = list(set(agent_identifiers))

    # Add URLs - removed from BaseEntity
    # url_rels = details.get('url-rels', [])
    # urls: Dict[str, List[str]] = {}
    # for url_rel in url_rels:
    #     rel_type_url = url_rel.get('type')
    #     target_url = url_rel.get('url', {}).get('resource')
    #     if rel_type_url and target_url:
    #         if rel_type_url not in urls: urls[rel_type_url] = []
    #         if target_url not in urls[rel_type_url]: urls[rel_type_url].append(target_url)
    # if urls: data_dict["urls"] = urls

    # Add setlist
    if hasattr(model_class, "setlist"):  # Check if field exists
        data_dict["setlist"] = details.get("setlist")

    # --- Final Validation and Save ---
    try:
        instance = model_class(**data_dict)
        save_entity(instance)
        print(f"  -> Finished processing {mb_name} ({identifier})")
        return instance.identifier
    except ValidationError as ve:
        print(f"  -> Error validating final {hom_entity_type} ({identifier}): {ve}")
        return None


# --- Main Execution ---
if __name__ == "__main__":
    start_time = time.time()
    print("Starting JSON generation process...")
    print(f"Output directory: {DATA_DIR}")

    # Ensure base data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Clear cache at the start of each run
    PROCESSED_CACHE.clear()

    # --- Initialize MusicBrainz Client ---
    # TODO: Replace with actual contact email
    client = MusicBrainzClient(
        app_name="MusicHistoryJSONGenerator",
        app_version="0.2",
        contact="user@example.com",
    )

    # --- Define Data to Process ---
    # Using the TEST lists defined at the top
    musicians_to_process = MUSICIANS_TEST
    ensembles_to_process = MUSIC_ENSEMBLES_TEST
    instruments_to_process = INSTRUMENTS_TEST
    genres_to_process = MUSIC_GENRES_TEST
    albums_to_process = ALBUMS_TEST
    singles_to_process = SINGLES_TEST
    events_to_process = PERFORMANCE_EVENTS_TEST
    awards_to_process = AWARDS_TEST

    # Collect all artist names mentioned to ensure they are processed *before* releases/events if possible
    all_artists_mentioned: Dict[str, bool] = {}  # name -> is_ensemble
    for name in musicians_to_process:
        all_artists_mentioned[name] = False
    for name in ensembles_to_process:
        all_artists_mentioned[name] = True
    for _, artist in albums_to_process + singles_to_process:
        if artist not in all_artists_mentioned:
            # Guess type if not in initial lists (default to Musician)
            all_artists_mentioned[artist] = artist in ensembles_to_process
    # Artists involved in events might also need pre-processing, but process_event handles it.

    print(
        f"Unique artist names to process initially: {list(all_artists_mentioned.keys())}"
    )

    # --- Process Entities ---

    print("\n--- Processing Artists (Musicians & Ensembles) ---")
    # Process known artists first
    for name, is_ensemble in all_artists_mentioned.items():
        # process_artist handles cache check internally now
        process_artist(client, name, is_ensemble=is_ensemble)

    # Note: Artists needed for releases/events might be re-processed if lookup finds
    # MBID where previous attempt failed, or if more details are found. This is okay,
    # save_entity overwrites the JSON with the more complete data.

    print("\n--- Processing Instruments ---")
    for name in instruments_to_process:
        process_instrument(client, name)

    print("\n--- Processing Music Genres ---")
    for name in genres_to_process:
        process_genre(client, name)

    print("\n--- Processing Albums ---")
    for title, artist_name in albums_to_process:
        process_release(
            client, title, artist_name, release_type="Album"
        )  # Use correct case

    print("\n--- Processing Singles ---")
    for title, artist_name in singles_to_process:
        process_release(
            client, title, artist_name, release_type="Single"
        )  # Use correct case

    print("\n--- Processing Performance Events ---")
    for name in events_to_process:
        process_event(client, name)

    # --- Completion ---
    end_time = time.time()
    print("\n--- JSON Generation Complete ---")
    print(f"Data saved in '{DATA_DIR}' directory.")
    print(f"Total entities processed/saved in this run: {len(PROCESSED_CACHE)}")
    print(f"Total time: {end_time - start_time:.2f} seconds")