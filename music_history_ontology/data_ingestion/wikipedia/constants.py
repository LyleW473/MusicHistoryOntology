import json
with open("rdf_components/class_property_mappings.json", "r") as f:
    CLASS_PROPERTY_MAPPINGS = json.load(f)

print(CLASS_PROPERTY_MAPPINGS)
CLASSES = list(CLASS_PROPERTY_MAPPINGS.keys())
CLASSES.append("Other")
print(CLASSES)

_INFORMATION_EXTRACTION_QUERY_TEMPLATE = """
                        You are a strict JSON extractor. 
                        You will only output a valid JSON object that contains the extracted information, with no extra explanation, greeting, or commentary.
                        The output must be valid JSON and match the structure exactly as requested by the user.
                        For each field, if the information is not present in the text, not applicable, not clear or not available, output "None" for the field.
                        """

_SEARCH_QUERY_CLASSIFICATION_QUERY_TEMPLATE = """
                        You are a strict binary classifier that only outputs a valid JSON object.
                        You will only output a valid JSON object that contains the extracted information, with no extra explanation, greeting, or commentary.
                        The output must be valid JSON and match the structure exactly as requested by the user.
                        """

_ALIAS_GENERATION_QUERY_TEMPLATE = """
                        You are a strict alias generator.
                        You will only output a valid JSON object that contains the alias that you have generated, with no extra explanation, greeting, or commentary.
                        The output must be valid JSON and match the structure exactly as requested by the user.
                        """

_SEARCH_QUERY_GENERATION_QUERY_TEMPLATE = """
                        You are a strict search query generator.
                        You will only output a valid JSON object that contains the search query that you have generated, with no extra explanation, greeting, or commentary.
                        The output must be valid JSON and match the structure exactly as requested by the user.
                        """

_TIME_INTERVAL_GENERATION_QUERY_TEMPLATE = """
                        You are a strict JSON extractor. 
                        You will only output a valid JSON object that contains the extracted information, with no extra explanation, greeting, or commentary.
                        The output must be valid JSON and match the structure exactly as requested by the user.
                        For each field, if the information is not present in the text, not applicable, not clear or not available, output "None" for the field.
                        Focus on any additional instructions provided by the user.
                        """

_INFORMATION_EXTRACTION_EMBEDDING_TEMPLATE = """
                        Extract the following details from the sample text:
                        {bullet_points}

                        For each field, if the information is not present in the text, not applicable, not clear or not available, output "None" for the field.
                        If you cannot find the information for the field in the expected format, also output "None" for the field.
                        Output only the following JSON object with the extracted values. Do not include any explanation or extra text.

                        {json_fields}

                        Sample text:
                        \"\"\"{text}\"\"\"
                        """

_SEARCH_QUERY_CLASSIFICATION_EMBEDDING_TEMPLATE = """
                        You are a multi-class classifier.
                        Given a search query, accompanying context text (e.g., from Wikipedia) and a class hierarchy tree, output a JSON object with the "class" field,
                        representing the class that you think this instance belongs to within the class hierarchy tree. 
                        
                        If the search query something that relates to the class but is not a direct match, then it should not be assigned to that class. For example a book about 
                        Mozart or a biography about Mozart would be not be an instance for the class "Musician"; only the actual musician "Mozart" would be assigned to the 
                        "Musician" class. 
                        
                        If the search query is not related to the class at all or if you cannot determine which class this instance should belong to with high confidence, you should
                        classify this instance as the "Other" class.

                        For your prediction, if the predicted class is a subclass in the provided class hierarchy, separate the superclasses and subclass for them using a "." separator. 
                        For example:

                        - Thing.Place.GeographicalFeature.Address (For an Address instance)
                        - Thing.Release.Album (For an Album instance)
                        - Thing.MusicArtist.Musician.Female (For a Female Musician instance)

                        All classes derive from the superclass "Thing", so you must include it as the first class in your answer.
                        You must respond with a valid JSON object containing only the predicted class, and nothing else — no explanations, commentary, or greetings.

                        Return your result in the following format:

                        {{
                        "class": <predicted class>
                        }}

                        Example result for a female musician:
                        {{
                        "class": Thing.MusicArtist.Musician.Female
                        }}
                        
                        Search query:
                        \"\"\"{search_query}\"\"\"

                        Context text:
                        \"\"\"{context_text}\"\"\"

                        Class hierarchy:
                        \"\"\"{class_hierarchy_tree}\"\"\"
                        """
_ALIAS_GENERATION_EMBEDDING_TEMPLATE = """
                        You are an alias generator.
                        Given a search query, accompanying context text (e.g., from Wikipedia), a class hierarchy tree and the predicted class that this instance belongs to, output a 
                        JSON object with the "alias" field, representing the alias that you have generated for this instance. 

                        The main purpose of this alias is to be used as a label for the instance in the context of the class hierarchy tree. It must be intuitive, such that
                        two entities that relate to each other should have similar aliases. For example, for the musician "Mozart", the alias could be "Mozart" or "Mozart the musician".
                        For a book about Mozart, the alias could be "Book about Mozart" or "Mozart biography". The cosine similarity between the aliases of two entities should be high, 
                        such that they are similar to each other.

                        You must respond with a valid JSON object containing only the generated alias, and nothing else — no explanations, commentary, or greetings.

                        Return your result in the following format:

                        {{
                        "alias": <generated alias>
                        }}

                        Example result for a book about Mozart:
                        {{
                        "alias": Book about Mozart
                        }}
                        
                        Search query:
                        \"\"\"{search_query}\"\"\"

                        Context text:
                        \"\"\"{context_text}\"\"\"

                        Class hierarchy:
                        \"\"\"{class_hierarchy_tree}\"\"\"

                        Predicted class for this instance:
                        \"\"\"{predicted_class}\"\"\"
                        """
_SEARCH_QUERY_GENERATION_EMBEDDING_TEMPLATE = """
                        You are an search query generator.
                        Given a class hierarchy tree (displaying the classes within the ontology), the desired class that you are supposed
                        to generate a search query for and all of the generated queries thus far, output a JSON object with the 'search_query' field, 
                        representing the alias that search query you have generated. 

                        The main purpose of this search query is to be used to retrieve Wikipedia data related to the specfied class in the ontology. 
                        This query should be as accurate as possible in the context of the class provided. The search query should be related to an 
                        instance or concept in the real-world that could pass as an instance of the desired class. 
                        
                        The ontology is based in the context of the history of music. Therefore, for a class like 'Thing.InformationObject.Instrument', 
                        you should generate a search query for any known musical instrument in the real world e.g., 'Flute'. For more general classes/concepts 
                        such as the 'Thing.Place.SpatialObject.GeographicalFeature.Country', you can name any such country such as 'Germany' or 'France'. For 
                        even more general classes/concepts like "Thing", you are free to generate any instance/concept in the real world as long as it links to the
                        history of music, e.g., this could be a song name, a country, a concept, anything. 
                        
                        You may use the provided class hierarchy tree and mappings displaying the object and data properties for the desired class to help you 
                        think about what instances could be generated. Your generated query should NOT already exist in the provided list of all generated queries.
                        If it is an alias that references the same instance that exists within the list of all generated queries, think of a different instance.
                        If you cannot think of an instance, set the 'search_query' field as 'None'.
                        
                        For example, if the desired class was "Thing.Release.Single", for the actual song 'Superhero' from the
                        'Heroes & Villains' album from 'Metro Boomin', a search query such as 'Superhero' is not sufficient, as it would map
                        to a class that does not exist within the ontology. The 'Superhero' query is likely to reference a benevolent fictional
                        character with superhuman powers. However, a query like 'Superhero (Heroes & Villains)' is much better and is likely to be 
                        an instance of the desired class. In general, you should generate queries that are likely to relate to instances of the desired 
                        class, keeping them as accurate as possible.

                        You must respond with a valid JSON object containing only the generated search query, and nothing else — no explanations, commentary, or greetings.

                        Return your result in the following format:

                        {{
                        "search_query": <generated search query>
                        }}

                        Example result for the song 'Superhero' from the 'Heroes & Villains' album made by 'Metro Boomin'
                        {{
                        "search_query": Superhero (Heroes & Villains)
                        }}
                        
                        Desired class:
                        \"\"\"{desired_class}\"\"\"

                        Class hierarchy:
                        \"\"\"{class_hierarchy_tree}\"\"\"

                        Property mappings for desired class:
                        \"\"\"{property_mappings_for_class}\"\"\"

                        All generated queries:
                        \"\"\"{all_generated_queries}\"\"\"
                        """

_TIME_INTERVAL_GENERATION_EMBEDDING_TEMPLATE = """
                        You are a strict JSON extractor.

                        You are expected to generate a JSON that contains a list of all the time intervals that you have extracted from the text along
                        with a corresponding alias for each time interval. The alias should be a human-readable string that describes the time interval.
                        For example given a page about "Mozart", you should add a time interval of "1756-1791" to the list, with the alias being something
                        like "Mozart's lifetime". This alias should be intuitive and unique to the time interval. Your alias should always end with the
                        words "time interval" or "time period". For example, "Mozart's lifetime time interval" or "Mozart's lifetime time period".

                        For each interval you should extract the following fields:
                        {bullet_points}

                        For each field, if the information is not present in the text, not applicable, not clear or not available, output "None" for the field.
                        If you cannot find the information for the field in the expected format, also output "None" for the field.

                        Output only the following JSON object with the extracted values. Do not include any explanation or extra text.

                        The format should be as follows:
                        {{
                        "time_intervals": {{
                            <unique-generated-alias>:{json_fields},
                            ...,
                            }}
                        }}

                        For example for a search query about a Violin object, you should return a JSON object that looks similar to this:
                        "time_intervals": {{
                            "Violin's origin time interval": {{
                                "hasDataValue": "16th century",
                                "hasDescription": "The period when the violin was first known.",
                                "hasEndTime": "16th century",
                                "hasIntervalDate": "16th century",
                                "hasKeyword": "violin origin",
                                "hasName": "Violin's first appearance",
                                "hasNickname": "None",
                                "hasNote": "None",
                                "hasRegionDataValue": "Italy",
                                "hasSpecifications": "None",
                                "hasStartTime": "16th century",
                                "hasSynonym": "None",
                                "hasTitle": "Violin's early history",
                                "inXSDDateTime": "None"
                            }},
                            "Violin's evolution time interval": {{
                                "hasDataValue": "18th and 19th centuries",
                                "hasDescription": "The period of modifications to enhance the violin's sound.",
                                "hasEndTime": "19th century",
                                "hasIntervalDate": "18th-19th centuries",
                                "hasKeyword": "violin evolution",
                                "hasName": "Modifications of the violin",
                                "hasNickname": "None",
                                "hasNote": "None",
                                "hasRegionDataValue": "Europe",
                                "hasSpecifications": "None",
                                "hasStartTime": "18th century",
                                "hasSynonym": "None",
                                "hasTitle": "Violin's development through modifications",
                                "inXSDDateTime": "None"
                            }},
                            "Stradivari family production time interval": {{
                                "hasDataValue": "16th to 18th century",
                                "hasDescription": "The period when the fine instruments by the Stradivari family were produced.",
                                "hasEndTime": "18th century",
                                "hasIntervalDate": "16th-18th centuries",
                                "hasKeyword": "Stradivari instruments",
                                "hasName": "Production of Stradivari instruments",
                                "hasNickname": "None",
                                "hasNote": "None",
                                "hasRegionDataValue": "Brescia and Cremona, Italy",
                                "hasSpecifications": "None",
                                "hasStartTime": "16th century",
                                "hasSynonym": "None",
                                "hasTitle": "Production period of historic violins",
                                "inXSDDateTime": "None"
                            }}
                        }}

                        This means that you are returning a JSON with a single key "time_intervals" which contains a dictionary of dictionaries where the key is the
                        generated alias and the value is a JSON object containing information on the extracted time interval.

                        Sample text:
                        \"\"\"{text}\"\"\"
                        """


QUERY_TEMPLATES = {
                "information_extraction": _INFORMATION_EXTRACTION_QUERY_TEMPLATE,
                "search_query_classification": _SEARCH_QUERY_CLASSIFICATION_QUERY_TEMPLATE,
                "alias_generation": _ALIAS_GENERATION_QUERY_TEMPLATE,
                "search_query_generation": _SEARCH_QUERY_GENERATION_QUERY_TEMPLATE,
                "time_interval_generation": _TIME_INTERVAL_GENERATION_QUERY_TEMPLATE
                }

USER_EMBEDDING_TEMPLATES = {
        "information_extraction": _INFORMATION_EXTRACTION_EMBEDDING_TEMPLATE,
        "search_query_classification": _SEARCH_QUERY_CLASSIFICATION_EMBEDDING_TEMPLATE,
        "alias_generation": _ALIAS_GENERATION_EMBEDDING_TEMPLATE,
        "search_query_generation": _SEARCH_QUERY_GENERATION_EMBEDDING_TEMPLATE,
        "time_interval_generation": _TIME_INTERVAL_GENERATION_EMBEDDING_TEMPLATE
}
CLASSES_TO_JSON_FIELDS = {}
for cls, properties in CLASS_PROPERTY_MAPPINGS.items():
    if "data_properties" in properties:
        CLASSES_TO_JSON_FIELDS[cls] = {field:info_dict["range_name"] for field, info_dict in properties["data_properties"].items()}
    else:
        CLASSES_TO_JSON_FIELDS[cls] = {}

print(CLASSES_TO_JSON_FIELDS)
print()