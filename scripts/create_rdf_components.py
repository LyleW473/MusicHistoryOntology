import set_path
import json
import os
import shutil
from music_history_ontology.rdf_reading.class_property_mappings import create_class_property_mappings
from music_history_ontology.rdf_reading.hierarchy_tree import build_class_tree

if __name__ == "__main__":

    rdf_file_path = "history_of_music_ontology.rdf"
    rdf_save_path = "rdf_components"
    class_property_map = create_class_property_mappings(rdf_file_path=rdf_file_path)

    for key, value in class_property_map.items():
        print(key, value)
        print()

    if os.path.exists(rdf_save_path):
        shutil.rmtree(rdf_save_path)
    os.makedirs(rdf_save_path)
    
    # Save the class property mappings to a file for later use
    with open(f"{rdf_save_path}/class_property_mappings.json", "w") as f:
        json.dump(class_property_map, f, indent=4)

    # Create and save the class hierarchy, used for recursive binary classification
    class_hierarchy_tree = build_class_tree(rdf_file_path=rdf_file_path)
    with open(f"{rdf_save_path}/class_hierarchy_tree.json", "w") as f:
        json.dump(class_hierarchy_tree, f, indent=4)