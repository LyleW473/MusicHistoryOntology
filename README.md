# music-history-ontology

![Python Version](https://img.shields.io/badge/python-3.12-blue)
[![Managed by Poetry](https://img.shields.io/badge/managed%20by-poetry-blueviolet)](https://python-poetry.org/)
![Coverage](coverage-badge.svg)
![Tests](https://github.kcl.ac.uk/music-hisotry-ontology-team/music-history-ontology/actions/workflows/main.yml/badge.svg?branch=main)

# Wikipedia Ingestion
## Workflow

The process of ingesting data from Wikipedia involves these steps:
1.  **Install requirements**: Run `pip install -r requirements.txt` within your virtual environment in the command terminal.
2.  **Create RDF components**: Run the `scripts/create_rdf_components.py` script:  
    *How it works:* This script is used to generate components necessary for generating data instances in the Wikipedia data ingestion pipeline and also for the construction of the final knowledge graph.
3.  **Generate Wikipedia Instances**: Run the `scripts/fetch_wikipedia_data.py` script:  
    *How it works:* This script is used to generate the Wikipedia data instances and store them in a specified data directory.


# Constructing Knowledge Graph
## Workflow
The process for creating a knowledge graph:
1.  **Creating Knowledge graph**: Run the `scripts/create_final_ontology.py` script:  
    *How it works:* This script is used to create the final knowledge graph

# MusicBrainz Client

## Workflow

The process of ingesting data from MusicBrainz involves two main steps:

1.  **Generate Raw JSON Files**: Run the `generate_json_files.py` script:
    ```bash
    poetry run python -m music_history_ontology.data_ingestion.musicbrainz.generate_json_files
    ```
    *How it works:* This script utilizes the `musicbrainz.py` client to interact with the MusicBrainz API. It queries the API based on predefined lists of search terms (e.g., artist names, album titles) specified within the script. The client handles rate limiting and fetches detailed JSON data for each entity. The script then parses these JSON responses, validates the data using Pydantic models (defined in `models/pydantic_models.py`), and resolves relationships between entities (like linking artists to albums or members to ensembles).
    *Output:* It saves each processed entity as a separate JSON file in the `data/` directory, organized into subdirectories based on the entity type derived from the Pydantic model (e.g., `data/Musician/`, `data/Album/`, `data/Instrument/`). Key entity types generated include: `Musician`, `MusicEnsemble`, `Album`, `Single`, `Recording`, `Instrument`, `MusicGenre`, `PerformanceEvent`, `Place`, `Country`, `RecordLabel`, and `TimeInterval`.

2.  **Convert to Ontology Format**: Run the `convert_json_format.py` script:
    ```bash
    poetry run python -m music_history_ontology.data_ingestion.musicbrainz.convert_json_format
    ```
    *How it works:* This script takes the raw, entity-specific JSON files generated in the previous step (located in `data/`) and transforms them into a format suitable for ontology population or other structured use cases. It reads the class and property mapping rules defined in `rdf_components/class_property_mappings.json`. Using these rules, it identifies the target ontology class for each entity (e.g., mapping a raw 'Musician' JSON to `Thing.MusicArtist.Musician`). It then restructures the properties from the raw JSON, aligning them with the expected object and data properties defined in the mappings.
    *Output:* The script consolidates all entities belonging to the same target class into a single output JSON file named after that class (e.g., `Thing.MusicArtist.Musician.json`). These consolidated files, containing standardized data structures, are saved in the `musicbrainz_data/` directory.
