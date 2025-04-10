import wikipedia
import random

from typing import Tuple, List, Dict, Any, Union
from music_history_ontology.data_ingestion.wikipedia.llm import LLMTextGenerator
from music_history_ontology.data_ingestion.wikipedia.instance import DataInstance

def retrieve_first_wikipedia_page(search_term:str="Mozart") -> Union[
                                                                    Tuple[str, wikipedia.WikipediaPage],
                                                                    Tuple[None, None]
                                                                    ]:
    """
    Retrieves the first wikipedia page related to a search term.

    Args:
        search_term (str): The search term to find a wikipedia page for, e.g., Mozart.
    """
    # Search for possible IDs related to a search term
    try: 
        possible_ids = wikipedia.search(search_term)
    except Exception as e: # Most likely a case with being too busy
        print("Error searching for Wikipedia page:", e)
        return None, None


    # Assume None for both in case no page is found
    possible_id = None
    first_page = None
    
    # Fetch the data for the first possible ID
    for i in range(len(possible_ids)):
        try:
            first_page = wikipedia.page(possible_ids[i])
            possible_id = possible_ids[i]
            break
        except wikipedia.DisambiguationError as e:
            print("DisambiguationError:", e)
            continue
        except wikipedia.PageError as e:
            print("PageError:", e)
            continue
    return possible_id, first_page

def filter_search_queries(
        search_query_classifier:LLMTextGenerator, 
        search_queries:List[str], 
        class_hierarchy_tree:str,
        known_classes:set[str]
        ) -> List[DataInstance]:
    """
    Filters search queries to remove any search queries that are classified as "Other". (DEPRECATED)

    Args:
        search_query_classifier (LLMTextGenerator): The LLMTextGenerator instance for search query classification.
        search_queries (List[str]): List of search queries to filter.
        class_hierarchy_tree (str): The string equivalent of the class hierarchy tree JSON for the ontology.
        known_classes (set[str]): A set containing the classes that exist in the ontology.
    """
    new_search_queries = []
    for search_query in search_queries:
        _, base_page = retrieve_first_wikipedia_page(search_term=search_query)

        if base_page is None:
            print(f"Page not found for search query: {search_query}")
            continue
        predicted_class = search_query_classifier.execute(
                                                            text=base_page.summary, 
                                                            search_query=search_query, 
                                                            class_hierarchy_tree=class_hierarchy_tree,
                                                            )
        if predicted_class is None:
            continue
        predicted_class = predicted_class["class"]
        print("Predicted class", predicted_class)
        print(known_classes)
        if predicted_class not in known_classes:
            continue
        if predicted_class == "Other":
            continue
        data_instance = DataInstance(
                                    search_query=search_query, 
                                    predicted_class=predicted_class
                                    )
        new_search_queries.append(data_instance)

    return new_search_queries

def get_initial_search_queries(
                            initial_queries_dict:Dict[str, List[str]], 
                            class_property_mappings:Dict[str, Any],
                            max_num_queries:Union[int, None]=None
                            ) -> List[DataInstance]:
    """
    Retrieves the initial search queries from the initial queries dictionary.
    - This is used to create the initial search queries for ingesting instance data from Wikipedia.
    - The initial queries are the search queries that are used to retrieve the data from Wikipedia.
    - From these initial queries, we can branch out to other search queries via related pages.
    - The defined initial queries should have a set class that is defined in the ontology.

    Args:
        initial_queries_dict (Dict[str, List[str]]): The dictionary mapping class names to a list of initial search queries.
        class_property_mappings (Dict[str, Any]): The dictionary mapping class names to their properties.
    """
    search_queries = []
    for class_name, queries in initial_queries_dict.items():
        for query in queries:
            data_instance = DataInstance(
                                        predicted_class=class_name,
                                        search_query=query
                                        )
            search_queries.append(data_instance)
            assert class_name in class_property_mappings.keys(), f"Class {class_name} not found in class_property_mappings"

    # Shuffle search queries (for greater class coverage)
    random.shuffle(search_queries)

    if max_num_queries is not None:
        search_queries = search_queries[:max_num_queries]
    return search_queries

def retrieve_related_pages(
                            search_query_classifier:LLMTextGenerator,
                            related_pages:List[str], 
                            num_to_search_for:int,
                            class_hierarchy_tree:str,
                            known_classes:set[str],
                            max_retrieval_per_query:int
                            ) -> List[DataInstance]:
    """
    Retrieves related pages from a list of search queries.

    Args:
        search_query_classifier (LLMTextGenerator): The LLMTextGenerator instance for search query classification.
        related_pages (List[str]): List of search queries to retrieve related pages for.
        num_to_search_for (int): The number of search queries to retrieve.
        class_hierarchy_tree (str): The string equivalent of the class hierarchy tree JSON for the ontology.
        known_classes (set[str]): A set containing the classes that exist in the ontology.
        max_retrieval_per_query (int): The maximum number of data to retrieve for the related pages from the base search query.
    """

    additional_search_queries = []
    num_added = 0

    # Shuffle related pages (as they are ordered by alphabetical order)
    random.shuffle(related_pages)

    for other_search_query in related_pages:
        if num_added >= num_to_search_for or num_added >= max_retrieval_per_query:
            break
        _, page = retrieve_first_wikipedia_page(search_term=other_search_query)
        if page is None:
            print(f"Page not found for search query: {other_search_query}")
            continue
        predicted_class = search_query_classifier.execute(
                                                            text=page.summary, 
                                                            search_query=other_search_query, 
                                                            class_hierarchy_tree=class_hierarchy_tree,
                                                            )
        if predicted_class is None:
            continue
        predicted_class = predicted_class["class"]
        if predicted_class not in known_classes:
            continue
        if predicted_class == "Other":
            continue

        print(f"Other search query {other_search_query} | Predicted class: {predicted_class}")
        data_instance = DataInstance(
                                    search_query=other_search_query, 
                                    predicted_class=predicted_class
                                    )
        additional_search_queries.append(data_instance)
        num_added += 1
    return additional_search_queries