from typing import Dict, Any, List
from slugify import slugify
from copy import deepcopy

from music_history_ontology.data_ingestion.wikipedia.instance import DataInstance
from music_history_ontology.data_ingestion.wikipedia.llm import LLMTextGenerator
from music_history_ontology.data_ingestion.wikipedia.constants import CLASSES_TO_JSON_FIELDS, CLASS_PROPERTY_MAPPINGS

class TimeIntervalInstanceGenerator:

    def __init__(self, class_property_mappings):
        self.ti_obj_props = self.find_time_interval_object_properties(
                                                        class_property_mappings=class_property_mappings
                                                        )
        self.llm = LLMTextGenerator(role="time_interval_generation")

    def find_time_interval_object_properties(self, class_property_mappings:Dict[str, Any]) -> set[str]:
        """
        Finds all the object properties in the ontology whcih map to the class "Thing.TimeInterval".
        - This will help identify whenever we need to create a new instance of the class "Thing.TimeInterval".
        - This is used to create the time interval instances in the Wikipedia data.

        Args:
            class_property_mappings (Dict[str, Any]): A mapping of classes to their properties and data types.
        """
        time_interval_obj_props = set()

        for c_class, class_info_dict in class_property_mappings.items():
            # print(f"Class: {c_class} | {class_info_dict.keys()}")
            class_obj_props = class_info_dict["object_properties"]
            for obj_prop, obj_prop_info_dict in class_obj_props.items():
                if obj_prop == "hasTimeInterval": # Maps owl:Thing -> Thing.TimeInterval, Thing is too general, so we ignore it
                    continue
                range_names = obj_prop_info_dict["range_names"]
                if "Thing.TimeInterval" in range_names:
                    time_interval_obj_props.add(obj_prop)
        #             print(f"Found object property: {obj_prop} with range names: {range_names}")
        # print(time_interval_obj_props)
        return time_interval_obj_props
    
    def execute(self, data_instance:DataInstance, page_summary:str) -> List[DataInstance]:
        """
        Generates instances of the class "Thing.TimeInterval" for the given data instance
        when the data instance has an object property that maps to the class "Thing.TimeInterval".
        - This is done by calling the LLM to generate the time interval information.
        - The generated time interval instances are linked to the subject data instance.

        Args:
            data_instance (DataInstance): The data instance for which to generate time interval instances.
            page_summary (str): The summary of the Wikipedia page for the data instance.
        """
        data_instance_information = data_instance.json_data
        data_instance_obj_props = data_instance_information["object_properties"]
        # print(data_instance_obj_props)

        ti_class_json_structure = CLASSES_TO_JSON_FIELDS["Thing.TimeInterval"]

        all_generated_ti_instances = [] # List of all generated time interval instances
        for obj_prop, obj_prop_info_dict in data_instance_obj_props.items():
            # print(obj_prop, obj_prop_info_dict.keys())

            # Not a time interval object property
            if obj_prop not in self.ti_obj_props:
                continue

            print(f"Creating instance of the class 'Thing.TimeInterval' for property: {obj_prop}")

            extracted_info_json = self.llm.execute(
                                                    text=page_summary,
                                                    json_structure=ti_class_json_structure,
                                                    )
            print("JSON Answer", extracted_info_json)
            if extracted_info_json is None:
                print("Failed to extract time interval information.")
                continue

            time_intervals_dict = extracted_info_json["time_intervals"]
            for generated_alias, time_interval_data_props_dict in time_intervals_dict.items():
                # print(f"Generated alias: {generated_alias}")
                # print(f"Time interval data properties: {time_interval_data_props_dict}")

                # Convert to a better alias
                slugify_alias = slugify(generated_alias)
                # print(generated_alias, slugify_alias)

                # Add the subject data instance's ID to the inverse object property
                ti_obj_props = deepcopy(CLASS_PROPERTY_MAPPINGS["Thing.TimeInterval"]["object_properties"])
                ti_obj_props["isTimeIntervalOf"]["ids"].append(data_instance.id)
                # print(ti_obj_props)

                ti_json_data = {
                    "object_properties": ti_obj_props,
                    "data_properties": time_interval_data_props_dict
                    }
                
                ti_data_instance = DataInstance(
                                            predicted_class="Thing.TimeInterval",
                                            search_query=slugify_alias,
                                            alias=slugify_alias,
                                            json_data=ti_json_data
                                            )
                all_generated_ti_instances.append(ti_data_instance)

                # Link this time interval instance to the subject data instance
                # print(data_instance.json_data["object_properties"][obj_prop]["ids"])
                data_instance.json_data["object_properties"][obj_prop]["ids"].append(ti_data_instance.id)
                # print(data_instance.json_data["object_properties"][obj_prop]["ids"])
                # print()

        print(f"Num time interval instances created: {len(all_generated_ti_instances)}")
        return all_generated_ti_instances