import uuid
from typing import Dict, Any

class DataInstance:
    def __init__(
                self, 
                predicted_class:str=None, 
                search_query:str=None, 
                alias:str=None, 
                json_data:Dict[str, Any]=None
                ):
        self.id = str(uuid.uuid4()) # Unique identifier for the instance
        self.predicted_class = predicted_class
        self.search_query = search_query
        self.alias = alias
        self.json_data = json_data

    def set_alias(self, alias:str):
        self.alias = alias
    
    def set_search_query(self, search_query:str):
        self.search_query = search_query
    
    def set_predicted_class(self, predicted_class:str):
        self.predicted_class = predicted_class

    def set_json_data(self, json_data:Dict[str, Any]):
        self.json_data = json_data

    def convert_to_json(self) -> Dict[str, Any]:
        """
        Converts the DataInstance object to a JSON-compatible dictionary.
        """
        if self.json_data is None:
            json_data = self.json_data
        else:
            # Remove any data properties that are None (Reduces the size of the JSON object)
            new_data_props = {}
            for data_prop, value in self.json_data["data_properties"].items():
                if value is None:
                    continue
                new_data_props[data_prop] = value
            json_data = {
                        "object_properties": self.json_data["object_properties"], 
                        "data_properties": new_data_props
                        }
        return {
            "id": self.id,
            "predicted_class": self.predicted_class,
            "search_query": self.search_query,
            "alias": self.alias,
            "json_data": json_data
            }
    