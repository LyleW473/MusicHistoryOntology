import set_path
import rdflib
import time
from sentence_transformers import SentenceTransformer
from music_history_ontology.ontology_enriching.faiss import load_linking_components
from music_history_ontology.data_ingestion.wikipedia.constants import CLASS_PROPERTY_MAPPINGS
from music_history_ontology.ontology_enriching.ontology_building import (
                                                                        find_linked_triples,
                                                                        find_instance_and_data_prop_triples, 
                                                                        find_obj_prop_triples, 
                                                                        enrich_existing_ontology,
                                                                        save_ontology_to_file
                                                                        )

if __name__ == "__main__":
    start_time = time.perf_counter()
    SCORE_THRESHOLD = 0.8 # Threshold for object property linking via aliases
    DATA_DIRS = [
                "generated_data/wikipedia",
                "generated_data/musicbrainz_converted",
                ]

    st_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    faiss_indexes, index_to_aliases_map, all_instances = load_linking_components(
                                                                                instance_data_dirs=DATA_DIRS,
                                                                                st_model=st_model
                                                                                )

    print(len(faiss_indexes), len(index_to_aliases_map))
    print(f"Num instances in ontology: {len(all_instances)}")

    # Define namespace 
    NS = rdflib.Namespace("http://www.semanticweb.org/lianmatsuo/ontologies/2025/2/history_of_music/")

    # 1. Add all RDF triples for instances and their data properties in the ontology
    instance_triples, data_property_triples = find_instance_and_data_prop_triples(
                                                                                all_instances=all_instances,
                                                                                class_property_mappings=CLASS_PROPERTY_MAPPINGS,
                                                                                namespace=NS
                                                                                )
    
    for instance_triple in instance_triples:
        subject, predicate, obj = instance_triple
        print(f"Triple: {subject} - {predicate} -> {obj}")

    for data_property_triple in data_property_triples:
        subject, predicate, obj = data_property_triple
        print(f"Triple: {subject} - {predicate} -> {obj}")
    
    # 2. Add all object properties for instances in the ontology
    linked_obj_prop_triples = find_linked_triples(
                                                all_instances=all_instances,
                                                namespace=NS,
                                                )
    print("Linked obj prop triples:")
    for triple in linked_obj_prop_triples:
        subject, predicate, obj = triple
        print(f"Triple: {subject} - {predicate} -> {obj}")

    obj_prop_triples = find_obj_prop_triples(
                                        all_instances=all_instances,
                                        st_model=st_model,
                                        faiss_indexes=faiss_indexes,
                                        index_to_aliases_map=index_to_aliases_map,
                                        namespace=NS,
                                        score_threshold=SCORE_THRESHOLD,
                                        )
    print("Obj prop triples:")
    for triple in obj_prop_triples:
        subject, predicate, obj, score = triple
        print(f"Triple: {subject} - {predicate} -> {obj} | (Score: {score})")

    g = enrich_existing_ontology(
                                rdf_file_path="history_of_music_ontology.rdf",
                                instance_triples=instance_triples,
                                data_property_triples=data_property_triples,
                                obj_prop_triples=obj_prop_triples,
                                linked_obj_prop_triples=linked_obj_prop_triples,
                                )
    print("Graph:")
    for s, p, o in g:
        print(f"Final Triple: {s} - {p} -> {o}")

    # Save the graph to a file
    save_ontology_to_file(graph=g, save_path="enriched_history_of_music_ontology.rdf")
    end_time = time.perf_counter()
    print(f"Num instance triples: {len(instance_triples)}")
    print(f"Num data property triples: {len(data_property_triples)}")
    print(f"Num linked obj property triples: {len(linked_obj_prop_triples)}")
    print(f"Num object property triples: {len(obj_prop_triples)}")
    print(f"Num triples in ontology: {len(g)}")
    print(f"Time to construct knowledge graph: {end_time - start_time:.2f} seconds")