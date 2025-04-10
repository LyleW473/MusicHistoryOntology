import os
import json
from typing import Dict, Any, List, Tuple, Union
from music_history_ontology.data_ingestion.wikipedia.functions import retrieve_first_wikipedia_page
from music_history_ontology.data_ingestion.wikipedia.llm import LLMTextGenerator
from music_history_ontology.data_ingestion.wikipedia.instance import DataInstance

def generate_queries_per_class(
                            trimmed_class_property_mappings:Dict[str, Any],
                            class_hierarchy_tree:Dict[str, Any],
                            search_query_classifier:LLMTextGenerator,
                            known_classes:set[str],
                            num_queries_per_class:int=5,
                            all_generated_queries:List[str]=[],
                            max_attempts_per_query_multiplier:int=3,
                            ) -> Dict[str, List[DataInstance]]:
    """
    Generates search queries for each class in the ontology using a search query generator.
    - Used to ensure that there is better class coverage for instances
      within the ontology.
    - Creates a set of unique search queries for each class and then classifies them, ensuring 
      that they are likely to be the expected class.
    
    Args:
        trimmed_class_property_mappings (Dict[str, Any]): The trimmed version of the class property mappings (i.e., no property URIs).
        class_hierarchy_tree (Dict[str, Any]): A hierarchy tree of all classes within the ontology.
        search_query_classifier (LLMTextGenerator): The search query classifier object.
        known_classes (set[str]): The set of known classes in the ontology.
        num_queries_per_class (int): The number of unique search queries to generate for each class, e.g., 5 instances per class.
        all_generated_queries (List[str]): A list of all previously generated search queries to avoid duplicate search queries.
        max_attempts_per_query_multiplier (int): A multiplier for the maximum number of attempts to generate a search query that aligns 
                                                with the expected class. The total number of max attempts would then be 
                                                (num_queries_per_class * max_attempts_per_query_multiplier).
    """
    search_query_generator = LLMTextGenerator(role="search_query_generation")
    generated_search_queries = {c_class:{} for c_class in trimmed_class_property_mappings.keys()} # Ensure there are unique queries for each class
    max_attempts_per_query = num_queries_per_class * max_attempts_per_query_multiplier

    for c_class in trimmed_class_property_mappings.keys():
        if c_class == "Thing": # Too general, skip
            continue
        print(f"Class: {c_class}")
        property_mappings_for_class = trimmed_class_property_mappings[c_class] # Select mappings for just the given class (optimisation)

        # Generate "num_queries_per_class" unique queries
        num_attempts = 0
        while (len(generated_search_queries[c_class]) < num_queries_per_class) and (num_attempts < max_attempts_per_query):

            # Generate search query
            print("Q", all_generated_queries)
            generated_search_query_json = search_query_generator.execute(
                                                            desired_class=c_class,
                                                            class_hierarchy_tree=class_hierarchy_tree,
                                                            property_mappings_for_class=property_mappings_for_class,
                                                            all_generated_queries=all_generated_queries,
                                                            )
            if generated_search_query_json is None:
                num_attempts += 1
                continue
            generated_search_query = generated_search_query_json["search_query"]
            print(f"Generated search query: {generated_search_query}")

            # Classify to check if it is likely to be the desired class, otherwise generate different query
            predicted_class = get_predicted_class(
                                                search_query_classifier=search_query_classifier,
                                                search_query=generated_search_query,
                                                expected_class=c_class,
                                                class_hierarchy_tree=class_hierarchy_tree,
                                                known_classes=known_classes
                                                )
            print("Predicted class", predicted_class, "Expected class", c_class)
            if predicted_class is None:
                print("Predicted class is None, continue")
                num_attempts += 1
                continue

            # Predicted is the same as expected or is a subclass of the expected class
            if (predicted_class == c_class) or is_subclass(predicted_class=predicted_class, expected_class=c_class):
                if predicted_class == c_class:
                    target_class = c_class # Add to the main class list of generated queries
                else:
                    target_class = predicted_class # Add to the subclass list of generated queries
                data_instance = DataInstance(predicted_class=target_class, search_query=generated_search_query)
                generated_search_queries[target_class][generated_search_query] = data_instance
            else:
                print("Not a subclass of the expected class")
                num_attempts += 1
                continue
            all_generated_queries.append(generated_search_query)

            for c_class, data_instance_dict in generated_search_queries.items():
                print(f"Class: {c_class} | Num queries: {len(data_instance_dict)}")
    
    return generated_search_queries

def is_subclass(predicted_class:str, expected_class:str):
    """
    Checks if the predicted class is a subclass of the expected class.
    - E.g., predicted=Thing.Agent.Person.Female.Musician.Female, expected=Thing.Agent, this should
      be valid.

    Args:
        predicted_class (str): The predicted class to check.
        expected_class (str): The expected class to check against.
    """
    return predicted_class.startswith(f"{expected_class}.") and (predicted_class != expected_class)

def get_predicted_class(
                        search_query_classifier:LLMTextGenerator,
                        search_query:str, 
                        expected_class:str, 
                        class_hierarchy_tree:Dict[str, Any], 
                        known_classes:set[str]
                        ) -> Union[None, str]:
    """
    Checks if the search query is likely to be the expected class using
    a search query classifier.

    Args:
        search_query_classifier (LLMTextGenerator): The search query classifier object.
        search_query (str): The search query to check.
        expected_class (str): The expected class for the search query.
        class_hierarchy_tree (Dict[str, Any]): A hierarchy tree of all classes within the ontology.
        known_classes (set[str]): The set of known classes in the ontology.
    """
            
    _, base_page = retrieve_first_wikipedia_page(search_term=search_query)

    if base_page is None:
        print(f"Page not found for search query: {search_query}")
        return None
    predicted_class = search_query_classifier.execute(
                                                        text=base_page.summary, 
                                                        search_query=search_query, 
                                                        class_hierarchy_tree=class_hierarchy_tree,
                                                        )
    if predicted_class is None:
        return None
    predicted_class = predicted_class["class"]
    print("Predicted class", predicted_class, "Expected class", expected_class)
    if predicted_class not in known_classes:
        return None
    return predicted_class


def get_generated_search_queries(
                                trimmed_class_property_mappings:Dict[str, Any],
                                class_hierarchy_tree:Dict[str, Any],
                                search_query_classifier:LLMTextGenerator,
                                known_classes:set[str],
                                all_generated_queries:List[str],
                                num_queries_per_class:int=5,
                                ):
    """
    Function for loading or creating the generated search queries for each class 
    in the ontology.

    Args:
        trimmed_class_property_mappings (Dict[str, Any]): The trimmed version of the class property mappings (i.e., no property URIs).
        class_hierarchy_tree (Dict[str, Any]): A hierarchy tree of all classes within the ontology.
        search_query_classifier (LLMTextGenerator): The search query classifier object.
        known_classes (set[str]): The set of known classes in the ontology.
        all_generated_queries (List[str]): A list of all previously generated search queries to avoid duplicate search queries.
        num_queries_per_class (int): The number of unique search queries to generate for each class, e.g., 5 instances per class.
    """
    if os.path.exists("rdf_components/automatic_generated_queries.json"):
        with open("rdf_components/automatic_generated_queries.json") as f:
            generated_search_queries = json.load(f)

        # Convert the JSON data back into DataInstance objects
        for c_class, data_instances_dict in generated_search_queries.items():
            for search_query, data_instance_json in data_instances_dict.items():
                generated_search_queries[c_class][search_query] = DataInstance(
                                                                        predicted_class=data_instance_json["predicted_class"],
                                                                        search_query=data_instance_json["search_query"],
                                                                        alias=data_instance_json["alias"],
                                                                        json_data=data_instance_json["json_data"]
                                                                        )
        print(generated_search_queries)
        print()
    else:
        generated_search_queries = generate_queries_per_class(
                                                            trimmed_class_property_mappings=trimmed_class_property_mappings,
                                                            class_hierarchy_tree=class_hierarchy_tree,
                                                            search_query_classifier=search_query_classifier,
                                                            known_classes=known_classes,
                                                            num_queries_per_class=num_queries_per_class,
                                                            all_generated_queries=all_generated_queries
                                                            ) 
        # Convert the generated search queries into a JSON format 
        # (which can be saved as a file, DataInstance objects cannot be saved as JSON)
        converted_generated_search_queries = {}
        for c_class, data_instances_dict in generated_search_queries.items():
            converted_generated_search_queries[c_class] = {}
            for search_query, data_instance in data_instances_dict.items():
                converted_generated_search_queries[c_class][search_query] = data_instance.convert_to_json()
        
        with open("rdf_components/automatic_generated_queries.json", "w") as f:
            json.dump(converted_generated_search_queries, f, indent=4)

    return generated_search_queries