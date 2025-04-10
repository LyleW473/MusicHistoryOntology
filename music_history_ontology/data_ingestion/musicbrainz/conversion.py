import os
import json
import glob

from copy import deepcopy
from slugify import slugify

def convert_files(data_folder, output_folder, class_mappings_file):
    """
    Convert JSON files from the data folder to the new format and save to the output folder.

    Args:
        data_folder (str): Path to the folder containing original JSON files
        output_folder (str): Path to save the converted files
        class_mappings_file (str): Path to the class property mappings file
    """
    # Load class property mappings
    with open(class_mappings_file, "r") as f:
        class_property_mappings = json.load(f)

    # Create output directory if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Define custom mappings for entity types to class names
    entity_type_to_class = {
        "Single": "Thing.Release.Single",
        "Album": "Thing.Release.Album",
        "PerformanceEvent": "Thing.Event.PerformanceEvent",
        "Country": "Thing.Place.SpatialObject.GeographicalFeature.Country",
        "Musician": "Thing.MusicArtist.Musician",
        "MusicEnsemble": "Thing.MusicArtist.MusicEnsemble",
    }
    
    # Get all subdirectories in the data folder
    data_dirs = [
        d
        for d in os.listdir(data_folder)
        if os.path.isdir(os.path.join(data_folder, d))
    ]

    for entity_type in data_dirs:
        # Get class name from mapping or use default
        if entity_type in entity_type_to_class:
            entity_class_name = entity_type_to_class[entity_type]
        else:
            entity_class_name = f"Thing.{entity_type}"

        # Skip if this class is not in the mappings
        if entity_class_name not in class_property_mappings:
            print(
                f"Warning: Class {entity_class_name} not found in property mappings, skipping"
            )
            continue

        # Output file path
        clean_entity_class_name = entity_class_name.replace(".", "_")
        output_file = os.path.join(output_folder, f"{clean_entity_class_name}.json")

        # Initialize the output structure
        output_data = {"class_name": entity_class_name, "data": []}

        # Get all JSON files for this entity type
        entity_files = glob.glob(os.path.join(data_folder, entity_type, "*.json"))

        for file_path in entity_files:
            # Load the original JSON
            with open(file_path, "r", encoding="utf-8") as f: # Read as UTF-8 to handle special characters
                print(f"Processing file: {file_path}")
                original_data = json.load(f)

            print(original_data)
            # Extract the identifier (without the prefix)
            identifier = original_data.get("identifier", "")
            id_parts = identifier.split("_")
            short_id = "_".join(id_parts[1:]) if len(id_parts) > 1 else identifier

            # Create the search query and alias
            name = original_data.get("hasName")
            if name == "Unknown":
                raise ValueError(f"Name is 'Unknown' for file: {file_path}")
            
            final_subclass_in_name = entity_class_name.split(".")[-1]
            alias = f"{name}-{entity_class_name}"
            alias = slugify(alias) # Turn it into a slug

            search_query = f"{name}-{final_subclass_in_name}"
            search_query = slugify(search_query) # Turn it into a slug

            base_class_data_props = deepcopy(class_property_mappings[entity_class_name]["data_properties"])
            base_class_obj_props = deepcopy(class_property_mappings[entity_class_name]["object_properties"])

            print(base_class_data_props.keys())
            print(base_class_obj_props.keys())

            # Remove all fields that are not data properties or object properties (we only want the data)
            instance_properties = deepcopy(original_data) 
            instance_properties.pop("hasName")
            instance_properties.pop("identifier")
            instance_properties.pop("entity_type")
            print(instance_properties)
            print()

            data_props_keep = []
            for prop_name, value in instance_properties.items():
                is_data_prop = (prop_name in base_class_data_props)
                is_obj_prop = (prop_name in base_class_obj_props)

                if is_data_prop:
                    # Add to data properties
                    base_class_data_props[prop_name] = value
                    data_props_keep.append(prop_name)

                if is_obj_prop:
                    base_class_obj_props[prop_name]["ids"].append(short_id)

                if not (is_data_prop or is_obj_prop):
                    # Skip data property, unknown to the ontology
                    print(f"Warning: Property {prop_name} not found in property mappings for {entity_class_name}, skipping")
                    continue
            
            # Remove data properties that don't have values.
            base_class_data_props = {k: v for k, v in base_class_data_props.items() if k in data_props_keep}

            new_entry = {
                "id": short_id,
                "predicted_class": entity_class_name,
                "search_query": search_query,
                "alias": alias,
                "json_data": {
                            "data_properties": base_class_data_props,
                            "object_properties": base_class_obj_props,
                            }
            }

            # Add the new entry to the output data
            output_data["data"].append(new_entry)

        # Save the output file
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=4)

        print(f"Converted {len(entity_files)} files for {entity_type} to {output_file}")