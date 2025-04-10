import set_path
import random
import os
import json
import time
from copy import deepcopy
from music_history_ontology.data_ingestion.wikipedia.functions import retrieve_first_wikipedia_page, get_initial_search_queries, retrieve_related_pages
from music_history_ontology.data_ingestion.wikipedia.llm import LLMTextGenerator
from music_history_ontology.data_ingestion.wikipedia.constants import CLASSES_TO_JSON_FIELDS, CLASSES, CLASS_PROPERTY_MAPPINGS
from music_history_ontology.data_ingestion.wikipedia.initial_queries import INITIAL_QUERIES_DICT
from music_history_ontology.data_ingestion.wikipedia.instance import DataInstance
from music_history_ontology.rdf_reading.class_property_mappings import create_trimmed_class_property_mappings
from music_history_ontology.data_ingestion.wikipedia.query_generation import get_generated_search_queries
from music_history_ontology.data_ingestion.wikipedia.time_interval_generator import TimeIntervalInstanceGenerator

if __name__ == "__main__":
    random.seed(42)

    
    search_query_classifier = LLMTextGenerator(role="search_query_classification")
    information_extractor = LLMTextGenerator(role="information_extraction")
    alias_generator = LLMTextGenerator(role="alias_generation")
    DATA_DIR = "generated_data/wikipedia"

    os.makedirs(DATA_DIR, exist_ok=True)

    NUM_DATA_FOR_ALL = 100 # The total number of data instances to retrieve for all classes (excluding TimeInterval instances)
    MAX_RETRIEVAL_PER_QUERY = 5 # The maximum number of relevant pages to retrieve for each search query (Lower=More variety)
    NUM_QUERIES_PER_CLASS_GENERATE = 3 # The number of initial queries to generate for each class.
    known_classes = set(CLASSES)

    with open("rdf_components/class_hierarchy_tree.json") as f:
        class_hierarchy_tree = json.load(f)
        class_hierarchy_tree = json.dumps(class_hierarchy_tree, indent=4)
    print(class_hierarchy_tree, type(class_hierarchy_tree))

    if os.path.exists("rdf_components/trimmed_class_property_mappings.json"):
        with open("rdf_components/trimmed_class_property_mappings.json") as f:
            trimmed_class_property_mappings = json.load(f)
    else:
        trimmed_class_property_mappings = create_trimmed_class_property_mappings(class_property_map=CLASS_PROPERTY_MAPPINGS)
        print(trimmed_class_property_mappings)
        with open("rdf_components/trimmed_class_property_mappings.json", "w") as f:
            json.dump(trimmed_class_property_mappings, f, indent=4)

    initial_search_queries = get_initial_search_queries(
                                                initial_queries_dict=INITIAL_QUERIES_DICT,
                                                class_property_mappings=CLASS_PROPERTY_MAPPINGS,
                                                max_num_queries=NUM_DATA_FOR_ALL
                                                )
    for i in range(len(initial_search_queries)):
        print(f"Search query: {initial_search_queries[i].search_query} | Set class: {initial_search_queries[i].predicted_class}")
    
    all_generated_queries = [data_instance.search_query for data_instance in initial_search_queries]
    print(all_generated_queries)
    generated_search_query_start_time = time.perf_counter()
    generated_search_queries = get_generated_search_queries(
                                                trimmed_class_property_mappings=trimmed_class_property_mappings,
                                                class_hierarchy_tree=class_hierarchy_tree,
                                                search_query_classifier=search_query_classifier,
                                                known_classes=known_classes,
                                                all_generated_queries=all_generated_queries,
                                                num_queries_per_class=NUM_QUERIES_PER_CLASS_GENERATE,
                                                )
    generated_search_query_end_time = time.perf_counter()
    time_taken_to_generate_search_queries = generated_search_query_end_time - generated_search_query_start_time
        
    for c_class, data_instance_dict in generated_search_queries.items():
        print(f"Class: {c_class} | Num queries: {len(data_instance_dict)}")
        for search_query, data_instance in data_instance_dict.items():
            print(f"Search query: {search_query} | Set class: {data_instance.predicted_class}")
        print()

    data_retrieval_start_time = time.perf_counter()
    # Aggregate all of the data instances into a single list.
    search_queries = [data_instance for data_instance in initial_search_queries]
    for c_class, data_instance_dict in generated_search_queries.items():
        generated_class_queries = data_instance_dict.values()
        print(generated_class_queries)
        search_queries.extend(generated_class_queries)

    # Start retrieval
    TIIG = TimeIntervalInstanceGenerator(class_property_mappings=CLASS_PROPERTY_MAPPINGS)
    data_for_each_class = {c_class: [] for c_class in CLASSES}
    print(data_for_each_class)
    total_data_retrieved = 0
    while len(search_queries) > 0 and total_data_retrieved < NUM_DATA_FOR_ALL:
        print(f"Number of search queries: {len(search_queries)}")
        base_data_instance = search_queries.pop(0) # Get the first search query
        base_search_query = base_data_instance.search_query
        base_predicted_class = base_data_instance.predicted_class

        _, base_page = retrieve_first_wikipedia_page(search_term=base_search_query)

        if base_page is None: # Cannot find page, so cannot extract info or get related pages
            print(f"Page not found for search query: {base_search_query}")
            continue

        text = base_page.summary
        class_json_structure = CLASSES_TO_JSON_FIELDS[base_predicted_class] # The json fields for the class we are interested in
        print(class_json_structure)
        extracted_info_json = information_extractor.execute(text=text, json_structure=class_json_structure)
        print("JSON Answer", extracted_info_json)
        print(base_search_query, base_predicted_class)
        if extracted_info_json is None:
            print("Failed to extract information.")
            continue

        # Generate the alias for the instance
        generated_alias_json = alias_generator.execute(
                                                text=text, 
                                                search_query=base_search_query, 
                                                class_hierarchy_tree=class_hierarchy_tree, 
                                                predicted_class=base_predicted_class
                                                )
        print(generated_alias_json)
        if generated_alias_json is None:
            print("Alias generation failed.")
            continue
        generated_alias = generated_alias_json["alias"]

        # Package the data into a single JSON object
        class_obj_props = CLASS_PROPERTY_MAPPINGS[base_predicted_class]["object_properties"] # Info on object properties
        json_data = {
            "object_properties": deepcopy(class_obj_props), # Deep copy because we need to add IDs later on for each separate instance
            "data_properties": extracted_info_json
            }

        data_instance = DataInstance(
                                    predicted_class=base_predicted_class, 
                                    search_query=base_search_query, 
                                    alias=generated_alias, 
                                    json_data=json_data
                                    )
        data_instance_json = data_instance.convert_to_json()
        print(data_instance_json)
        # Add data to the corresponding class
        total_data_retrieved += 1
        data_for_each_class[base_predicted_class].append(data_instance_json)
        print(f"Num data for class: {len(data_for_each_class[base_predicted_class])}")

        # Check if we need to create time interval instances
        generated_ti_data_instances = TIIG.execute(data_instance=data_instance, page_summary=text)
        for ti_data_instance in generated_ti_data_instances:
            # Note: Do not add to "total_data_retrieved", this does not count towards the total number of data instances we want to retrieve.
            ti_data_instance_json = ti_data_instance.convert_to_json()
            data_for_each_class[ti_data_instance.predicted_class].append(ti_data_instance_json)
        
        # Find related pages from the first possible ID and add them to the search queries
        related_pages = base_page.links
        num_to_search_for = max(NUM_DATA_FOR_ALL - len(search_queries) - total_data_retrieved, 0) # Limit to 0
        print(f"Num to search for: {num_to_search_for}")
        if num_to_search_for > 0:
            additional_search_queries = retrieve_related_pages(
                                                            search_query_classifier=search_query_classifier,
                                                            related_pages=related_pages,
                                                            num_to_search_for=num_to_search_for,
                                                            class_hierarchy_tree=class_hierarchy_tree,
                                                            known_classes=known_classes,
                                                            max_retrieval_per_query=MAX_RETRIEVAL_PER_QUERY
                                                            )
            search_queries.extend(additional_search_queries)
    
    for c_class, data_for_class in data_for_each_class.items():
        # Save all the JSON data aggregated for the class
        save_data = {"class_name": c_class, "data": data_for_class}
        print(f"Class: {c_class} | Num data for class: {len(data_for_class)}")
        clean_class_name = c_class.replace(".", "_") # E.g., Thing.Composers -> Thing_Composers
        with open(f"{DATA_DIR}/{clean_class_name}.json", "w") as f:
            json.dump(save_data, f, indent=4)

    data_retrieval_end_time = time.perf_counter()
    time_taken_to_retrieve_data = data_retrieval_end_time - data_retrieval_start_time
    print(f"Time taken to generate search queries: {time_taken_to_generate_search_queries:.5f} seconds")
    print(f"Time taken to retrieve data: {time_taken_to_retrieve_data:.5f} seconds")