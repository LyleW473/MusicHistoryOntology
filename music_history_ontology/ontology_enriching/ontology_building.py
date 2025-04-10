import rdflib
import faiss
from sentence_transformers import SentenceTransformer
from slugify import slugify
from typing import List, Dict, Any, Tuple

from music_history_ontology.ontology_enriching.utils import convert_data_prop_value
from music_history_ontology.rdf_reading.functions import convert_rdffile_to_graph

def find_linked_triples(all_instances:List[Dict[str, Any]], namespace:rdflib.Namespace) -> List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]]:
    """
    Creates RDF triples for instances which are linked via their 
    object properties, using the IDs for each instance.

    - We do not need to check for inverse properties here because if they are linked, they would have been
      linked in the inverse direction as well.

    Args:
        all_instances (List[Dict[str, Any]]): List of all instances as JSON dicts with their properties and values.
        namespace (rdflib.Namespace): Namespace for the ontology, used to create URIs for the instances.
    """

    ids_to_instances = {}
    for instance in all_instances:
        instance_id = instance["id"]
        ids_to_instances[instance_id] = instance
    print(ids_to_instances.keys())

    linked_triples = []
    for instance in all_instances:
        subject_alias = instance["alias"]
        subject_class = instance["predicted_class"]
        subject_id = instance["id"]
        
        print(f"Subject ID: {subject_id}")
        print(f"Subject alias: {subject_alias}")
        print(f"Subject class: {subject_class}")
        subject_obj_properties = instance["json_data"]["object_properties"]
        for obj_prop, obj_prop_info_dict in subject_obj_properties.items():
            print(f"Object property: {obj_prop}")
            linked_ids = obj_prop_info_dict["ids"]
            print(f"Linked IDs: {linked_ids}")

            for linked_id in linked_ids:
                if linked_id not in ids_to_instances:
                    print(f"Linked ID {linked_id} not found in instances")
                    raise ValueError(f"Linked ID {linked_id} not found in instances")
                
                linked_instance = ids_to_instances[linked_id]
                linked_alias = linked_instance["alias"]
                linked_class = linked_instance["predicted_class"]
                print(f"Subject alias: {subject_alias}")
                print(f"Subject class: {subject_class}")
                print(f"Linked alias: {linked_alias}")
                print(f"Linked class: {linked_class}")
                print(f"Linked ID: {linked_id}")
                print(f"Linked instance: {ids_to_instances[linked_id]['alias']}")
                
                # Create a triple for the object property
                obj_property_uri = obj_prop_info_dict["property_uri"]
                subject_uri = namespace[slugify(subject_alias)] # Create a URI for the subject (URIRef)
                linked_uri = namespace[slugify(linked_alias)] # Create a URI for the linked instance (URIRef)

                triple = (
                        subject_uri, # Subject
                        rdflib.URIRef(obj_property_uri), # Predicate
                        linked_uri # Object
                        )
                print(triple)
                linked_triples.append(triple)
    return linked_triples

def find_instance_and_data_prop_triples(
        all_instances:List[Dict[str, Any]],
        class_property_mappings:Dict[str, Any],
        namespace:rdflib.Namespace,
        ) -> Tuple[
                    List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]],
                    List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.Literal]]
                    ]:
    """
    Creates RDF triples for instances and their data properties in the ontology.

    Args:
        all_instances (List[Dict[str, Any]]): List of all instances as JSON dicts with their properties and values.
        class_property_mappings (Dict[str, Any]): Mappings of classes to their properties for the entire ontology.
        namespace (rdflib.Namespace): Namespace for the ontology, used to create URIs for the instances.
    """
    instance_triples = []
    data_property_triples = []

    for instance in all_instances:
        subject_alias = instance["alias"]
        subject_class = instance["predicted_class"]
        subject_class_uri = class_property_mappings[subject_class]["class_uri"] # URI for the class (e.g., Thing.AgentRole)
        subject_uri = namespace[slugify(subject_alias)] # Create a URI for the subject (URIRef)
        instance_triple = (
                    subject_uri, # Subject
                    rdflib.RDF.type, # Predicate
                    rdflib.URIRef(subject_class_uri) # Object
                    )
        print(instance_triple)
        instance_triples.append(instance_triple)

        # Add data property triples
        data_properties = instance["json_data"]["data_properties"]
        print(data_properties)
        for data_prop, data_prop_value in data_properties.items():
            if data_prop_value is None: # Skip data properties with None values
                continue
            data_prop_info_dict = class_property_mappings[subject_class]["data_properties"][data_prop]
            data_prop_range_uri = data_prop_info_dict["property_uri"]
            data_prop_datatype = data_prop_info_dict["range_name"]
            print(data_prop_range_uri, data_prop_value)

            # Convert to actual data property value e.g., xsd:string, xsd:integer, etc.
            data_prop_value = convert_data_prop_value(
                                                    data_property_datatype=data_prop_datatype,
                                                    data_property_value=data_prop_value
                                                    )
            data_property_triple = (
                                subject_uri, # Subject
                                rdflib.URIRef(data_prop_range_uri), # Predicate
                                data_prop_value, # Object
                                )
            print(data_property_triple)
            data_property_triples.append(data_property_triple)
    return instance_triples, data_property_triples

def find_obj_prop_triples(
        all_instances:List[Dict[str, Any]],
        st_model:SentenceTransformer,
        faiss_indexes:Dict[str, faiss.Index],
        index_to_aliases_map:Dict[str, Dict[int, str]], # Maps index to aliases
        namespace:rdflib.Namespace,
        score_threshold:float=0.75, # Threshold for similarity score
        ) -> List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]]:
    """
    Creates RDF triples for object properties in the ontology.

    Args:
        all_instances (List[Dict[str, Any]]): List of all instances as JSON dicts with their properties and values.
        st_model (SentenceTransformer): SentenceTransformer model for encoding aliases to embeddings.
        faiss_indexes (Dict[str, faiss.Index]): FAISS indexes for each class in the ontology, used for similarity search.
        index_to_aliases_map (Dict[str, Dict[int, str]]): Maps index to aliases.
        namespace (rdflib.Namespace): Namespace for the ontology, used to create URIs for the instances.
        score_threshold (float): Threshold for similarity score to consider a match.
    """
    used_objects = set() # Track used objects for inverse properties
    obj_prop_triples = [] # Store the object property triples

    for instance in all_instances:
        subject_class = instance["predicted_class"]
        subject_alias = instance["alias"] 
        if subject_class == "Thing.TimeInterval": # There is no need to link time intervals, since this has already been done
            continue
        subject_uri = namespace[slugify(subject_alias)] # Create a URI for the subject (URIRef)

        subject_alias_embedding = st_model.encode(subject_alias) # (,384)
        instance_data = instance["json_data"]
        instance_object_properties = instance_data["object_properties"]

        for obj_property, obj_prop_info_dict in instance_object_properties.items():
            range_classes = obj_prop_info_dict["range_names"]
            characteristics = obj_prop_info_dict["characteristics"]
            obj_property_uri = obj_prop_info_dict["property_uri"]
            # print(f"Object property: {obj_property}")
            # print(f"Range classes: {range_classes}")
            # print(f"Characteristics: {characteristics}")
            # print()

            is_func = characteristics.get("Functional", False)
            is_inverse = characteristics.get("InverseFunctional", False)
            is_transitive = characteristics.get("Transitive", False)
            is_sym = characteristics.get("Symmetric", False)
            is_asym = characteristics.get("Asymmetric", False)
            is_ref = characteristics.get("Reflexive", False)
            is_irref = characteristics.get("Irreflexive", False)

            for range_class in range_classes:
                if range_class == "Thing.TimeInterval": # There is no need to link time intervals, since this has already been done
                    continue

                if faiss_indexes.get(range_class) is None:
                    print(f"Range class {range_class} not found in indexes")
                    continue
                D, I = faiss_indexes[range_class].search(
                                                        subject_alias_embedding.reshape(1, -1), 
                                                        k=3)
                top_candidates = []
                for score, idx in zip(D[0], I[0]):
                    print(idx)
                    if idx == -1: # i.e., No match found for the the "kth" candidate.
                        continue
                    range_alias = index_to_aliases_map[range_class][idx]

                    print(f"Subject alias: {subject_alias} | Range alias: {range_alias} | Score: {score} | Property: {obj_property} | Subject class: {subject_class} | Range class: {range_class} | Characteristics: {characteristics}")

                    if range_alias == subject_alias: # Same instance
                        continue

                    if is_inverse and range_alias in used_objects:
                        continue
                    
                    # Skip reflexive if irreflexive
                    if is_irref and range_alias == subject_alias:
                        continue
                    
                    if score >= score_threshold: # Only add candidates with a score above the threshold
                        print(f"Adding candidate: {range_alias} with score: {score}")
                        top_candidates.append((range_alias, score))
                    
                if is_func:
                    top_candidates = top_candidates[:1]
                
                for range_alias, score in top_candidates:
                    range_uri = namespace[slugify(range_alias)] # Create a URI for the range (URIRef)
                    print(f"Object ID: {range_alias}")
                    print(f"Score: {score}")
                    print(f"Object property: {obj_property}")
                    obj_property_triple = (
                                            subject_uri, # Subject
                                            rdflib.URIRef(obj_property_uri), # Predicate
                                            range_uri, # Object
                                            score # TEMPORARY
                                            )
                    print(obj_property_triple)
                    obj_prop_triples.append(obj_property_triple)
                
                    if is_inverse:
                        used_objects.add(range_alias)

                    if is_sym:
                        # Add the inverse triple
                        inverse_obj_property_triple = (
                                                        range_uri, # Subject
                                                        rdflib.URIRef(obj_property_uri), # Predicate
                                                        subject_uri, # Object
                                                        score # TEMPORARY
                                                        )
                        obj_prop_triples.append(inverse_obj_property_triple)
                        print(inverse_obj_property_triple)
                        print()
    
    return obj_prop_triples

def enrich_existing_ontology(
                            rdf_file_path:str,
                            instance_triples:List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]],
                            data_property_triples:List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.Literal]],
                            obj_prop_triples:List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]],
                            linked_obj_prop_triples:List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]],
                            ) -> rdflib.Graph:
    """
    Enriches an existing ontology with new triples.

    Args:
        rdf_file_path (str): Path to the RDF file.
        instance_triples (List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]]): List of instance triples.
        data_property_triples (List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.Literal]]): List of data property triples.
        obj_prop_triples (List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]]): List of object property triples.
        linked_obj_prop_triples (List[Tuple[rdflib.URIRef, rdflib.URIRef, rdflib.URIRef]]): List of linked object property triples.
    """
    # Load existing graph
    g = convert_rdffile_to_graph(rdf_file_path=rdf_file_path)

    # Add all triples to a graph
    for triple in instance_triples:
        g.add(triple)
    for triple in data_property_triples:
        g.add(triple)
    for triple in obj_prop_triples:
        subject, predicate, obj, score = triple
        g.add((subject, predicate, obj))
    for triple in linked_obj_prop_triples:
        g.add(triple)
    return g

def save_ontology_to_file(graph:rdflib.Graph, save_path:str) -> None:
    """
    Saves the ontology graph as an RDF file.

    Args:
        save_path (str): Path to save the RDF file.
    """
    # Save the graph to a file
    graph.serialize(destination=save_path, format="xml")
    print(f"Graph saved to {save_path}")