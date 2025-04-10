import json
import os
import numpy as np
import faiss
import rdflib
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple
from collections import defaultdict

def load_linking_components(st_model:SentenceTransformer, instance_data_dirs:List[str]) -> Tuple[
                                                        Dict[str, faiss.Index], 
                                                        Dict[str, Dict[int, str]], 
                                                        List[Dict[str, str]]
                                                        ]:
    """
    Creates the components needed for linking instances to the ontology.
    - Creates a FAISS index for each class in the ontology.
    - Maps each index to the corresponding alias.
    - Loads all instances for later use.

    Args:
        instance_data_dir (str): Directory containing the instance data files.

    """
    # Load the instances
    all_instances = defaultdict(list) # Dictionary to store all instances for each class

    for data_dir in instance_data_dirs:
        for c_class in os.listdir(data_dir):
            with open(f"{data_dir}/{c_class}", "r") as f:
                instances = json.load(f)

            # Convert from Thing_AgentRole.json -> Thing.AgentRole
            c_class = c_class.replace("_", ".")
            c_class = c_class.replace(".json", "")

            # Skip empty classes
            if len(instances["data"]) < 1:
                continue
            
            all_instances[c_class].extend(instances["data"])

    all_instances = dict(all_instances) # Convert defaultdict to dict
    total_instances = sum([len(instances) for instances in all_instances.values()])
    
    # Generate FAISS indexes and mappings for each class
    faiss_indexes = {}
    index_to_aliases_map = {}

    for c_class, instances in all_instances.items():
        print(c_class)

        # Skip empty classes
        if len(instances) < 1:
            faiss_indexes[c_class] = None
            index_to_aliases_map[c_class] = None
            continue
            
        # Convert aliases to embeddings
        aliases = [instance["alias"] for instance in instances]
        embeddings = st_model.encode(aliases)
        print(embeddings.shape)

        # Create FAISS index for each class
        index = faiss.IndexFlatIP(embeddings.shape[1]) # Cosine similarity
        index.add(embeddings)

        # Store the index and mappings to aliases
        faiss_indexes[c_class] = index
        index_to_aliases_map[c_class] = {i: alias for i, alias in enumerate(aliases)}
    
    # Flatten the all_instances dictionary
    all_instances = [instance for instances in all_instances.values() 
                     for instance in instances] 
    
    for instance in all_instances:
        print(instance)
        print()

    num_faiss_instances = sum([index.ntotal for index in faiss_indexes.values() if index is not None])
    num_mappings = sum([len(mappings) for mappings in index_to_aliases_map.values() if mappings is not None])
    print(f"Num instances from FAISS: {num_faiss_instances}")
    print(f"Num instances in ontology {total_instances}")
    print(f"Num instances from mappings: {num_mappings}")

    assert num_faiss_instances == total_instances, \
        f"Num instances from FAISS: {num_faiss_instances} != Num instances in ontology {total_instances}"
    assert num_mappings == total_instances, \
        f"Num instances from mappings: {num_mappings} != Num instances in ontology {total_instances}"
    return faiss_indexes, index_to_aliases_map, all_instances