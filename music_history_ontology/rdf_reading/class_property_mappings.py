import rdflib
from collections import defaultdict
from typing import Dict, List
from music_history_ontology.rdf_reading.functions import convert_rdffile_to_graph, get_readable_name, get_all_class_paths, is_declared_class

def find_class_names_to_uris(rdf_graph:rdflib.Graph) -> List[str]:
    """
    Creates a mapping from a readable class name to their corresponding
    URI.

    Args:
        rdf_graph (rdflib.Graph): The graph object for the ontology.
    """
    class_names_to_uris = {}
    
    # Classes declared with owl:Class
    for cls in rdf_graph.subjects(rdflib.RDF.type, rdflib.OWL.Class):
        if isinstance(cls, rdflib.URIRef):
            cls_strs = get_all_class_paths(rdf_graph=rdf_graph, cls=cls)
            print(cls_strs)
            for cls_str in cls_strs:
                if cls_str not in class_names_to_uris:
                    class_names_to_uris[cls_str] = cls
                else:
                    raise ValueError(f"Duplicate class name: {cls_str} for {class_names_to_uris[cls_str]} and {cls}")

    # Classes declared with rdfs:Class
    for cls in rdf_graph.subjects(rdflib.RDF.type, rdflib.RDFS.Class):
        if isinstance(cls, rdflib.URIRef):
            cls_strs = get_all_class_paths(rdf_graph=rdf_graph, cls=cls)
            print(cls_strs)
            for cls_str in cls_strs:
                if cls_str not in class_names_to_uris:
                    class_names_to_uris[cls_str] = cls
                else:
                    raise ValueError(f"Duplicate class name: {cls_str} for {class_names_to_uris[cls_str]} and {cls}")
    return class_names_to_uris

def find_superclasses_for_each_class(rdf_graph:rdflib.Graph) -> Dict[str, List[str]]:
    """
    Creates a dict that maps classes to a list of all of their superclasses.

    Args:
        rdf_graph (rdflib.Graph): The graph object for the ontology.
    """
    class_names_to_uris = find_class_names_to_uris(rdf_graph=rdf_graph)
    
    superclasses_for_each_class = defaultdict(list)
    for class_name, class_uri in class_names_to_uris.items():
        print("Class URI", class_uri)
        superclasses_for_class = set()
        for superclass in rdf_graph.objects(class_uri, rdflib.RDFS.subClassOf):
            if isinstance(superclass, rdflib.URIRef):
                if is_declared_class(rdf_graph=rdf_graph, uri=superclass):
                    print("Superclass", superclass, "Subclass", class_uri)
                    print()
                    superclass_strs = get_all_class_paths(rdf_graph=rdf_graph, cls=superclass)
                    for superclass_str in superclass_strs:
                        if superclass_str not in superclasses_for_class:
                            superclasses_for_class.add(superclass_str)
        print(class_name, superclasses_for_each_class)
        superclasses_for_each_class[class_name] = list(superclasses_for_class)
        print(superclasses_for_each_class)
    print(superclasses_for_each_class)
    return superclasses_for_each_class

def merge_class_properties(rdf_graph:rdflib.Graph, class_property_map:Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Merges the data and object properties of a class with those of their superclasses.

    Args:
        rdf_graph (rdflib.Graph): The graph object for the ontology.
        class_property_map (Dict[str, Dict[str, str]]): A mapping of classes to their properties and 
                                                        the datatype of those properties.
    """

    superclasses_for_each_class = find_superclasses_for_each_class(rdf_graph=rdf_graph)

    thing_object_properties = class_property_map["Thing"]["object_properties"]
    thing_data_properties = class_property_map["Thing"]["data_properties"]

    # Merge the properties of each class with those of their superclasses:
    for class_name, superclasses in superclasses_for_each_class.items():
        if class_name not in class_property_map:
            raise ValueError(f"class {class_name} not in classes")

        # Add the object/data properties of each superclass to that of the subclass in the mappings.
        for superclass_name in superclasses:
            if superclass_name not in class_property_map:
                raise ValueError(f"superclass {superclass_name} not in classes")
            superclass_object_properties = class_property_map[superclass_name]["object_properties"]
            superclass_data_properties = class_property_map[superclass_name]["data_properties"]
            for obj_prop in superclass_object_properties:
                class_property_map[class_name]["object_properties"][obj_prop] = superclass_object_properties[obj_prop]
            for data_prop in superclass_data_properties:
                class_property_map[class_name]["data_properties"][data_prop] = superclass_data_properties[data_prop]

        # Add Thing properties (not in the superclasses)
        for obj_prop in thing_object_properties:
            class_property_map[class_name]["object_properties"][obj_prop] = thing_object_properties[obj_prop]
        for data_prop in thing_data_properties:
            class_property_map[class_name]["data_properties"][data_prop] = thing_data_properties[data_prop]
    return class_property_map

def get_obj_prop_characteristics(
        rdf_graph:rdflib.Graph, 
        obj_prop:rdflib.URIRef, 
        characteristics_keys:List[str]=["Functional", "InverseFunctional", "Transitive", "Symmetric", "Asymmetric", "Reflexive", "Irreflexive"]
        ) -> str:
    """
    Gets the characteristics of an object property and returns them as a dictionary.

    Args:
        rdf_graph (rdflib.Graph): The graph object for the ontology.
        obj_prop (rdflib.URIRef): The object property to check.
        characteristics_keys (List[str]): The characteristics to check for.
    """
    characteristics = {char:False for char in characteristics_keys}
    if (obj_prop, rdflib.RDF.type, rdflib.OWL.FunctionalProperty) in rdf_graph:
        characteristics["Functional"] = True
    if (obj_prop, rdflib.RDF.type, rdflib.OWL.InverseFunctionalProperty) in rdf_graph:
        characteristics["InverseFunctional"] = True
    if (obj_prop, rdflib.RDF.type, rdflib.OWL.TransitiveProperty) in rdf_graph:
        characteristics["Transitive"] = True
    if (obj_prop, rdflib.RDF.type, rdflib.OWL.SymmetricProperty) in rdf_graph:
        characteristics["Symmetric"] = True
    if (obj_prop, rdflib.RDF.type, rdflib.OWL.AsymmetricProperty) in rdf_graph:
        characteristics["Asymmetric"] = True
    if (obj_prop, rdflib.RDF.type, rdflib.OWL.ReflexiveProperty) in rdf_graph:
        characteristics["Reflexive"] = True
    if (obj_prop, rdflib.RDF.type, rdflib.OWL.IrreflexiveProperty) in rdf_graph:
        characteristics["Irreflexive"] = True
    return characteristics

def create_class_property_mappings(rdf_file_path:str) -> Dict[str, Dict[str, str]]:
    """
    Creates a mapping of classes to their properties and the datatype of those properties.

    Args:
        rdf_file_path (str): Path to the RDF file.
    """
    rdf_graph = convert_rdffile_to_graph(rdf_file_path=rdf_file_path)
    class_property_map = defaultdict(lambda:defaultdict(dict))
    
    # 1. Find all classes (Even if they have no properties)
    # Classes declared with owl:Class
    for cls in rdf_graph.subjects(rdflib.RDF.type, rdflib.OWL.Class):
        if isinstance(cls, rdflib.URIRef):
            cls_strs = get_all_class_paths(rdf_graph=rdf_graph, cls=cls)
            print(cls_strs)
            for cls_str in cls_strs:
                class_property_map[cls_str]
                class_property_map[cls_str]["object_properties"]
                class_property_map[cls_str]["data_properties"]

                cls_uri_ref = str(cls) 
                class_property_map[cls_str]["class_uri"] = cls_uri_ref

    # Classes declared with rdfs:Class
    for cls in rdf_graph.subjects(rdflib.RDF.type, rdflib.RDFS.Class):
        if isinstance(cls, rdflib.URIRef):
            cls_str = get_all_class_paths(rdf_graph=rdf_graph, cls=cls)
            print(cls_str)
            for cls_str in cls_strs:
                class_property_map[cls_str]
                class_property_map[cls_str]["object_properties"]
                class_property_map[cls_str]["data_properties"]

                cls_uri_ref = str(cls) 
                class_property_map[cls_str]["class_uri"] = cls_uri_ref

    # 2. Fill in properties per class if available.
    for prop in rdf_graph.subjects(rdflib.RDFS.domain, None):
        domain = rdf_graph.value(prop, rdflib.RDFS.domain)
        range_uri = rdf_graph.value(prop, rdflib.RDFS.range)

        if isinstance(domain, rdflib.URIRef) and isinstance(prop, rdflib.URIRef):
            # Extract class and property names
            # class_name = get_readable_name(domain)
            class_names = get_all_class_paths(rdf_graph, domain)
            property_name = get_readable_name(prop)
            print(class_names, property_name, domain, range_uri)
            
            for class_name in class_names:
                # Find data properties
                if (prop, rdflib.RDF.type, rdflib.OWL.DatatypeProperty) in rdf_graph:
                    if isinstance(range_uri, rdflib.URIRef):
                        range_name = get_readable_name(range_uri) # E.g., string, dateTime, Literal, etc..
                    else:
                        range_name = "Literal"
                    prop_uri = str(prop)
                    class_property_map[class_name]["data_properties"][property_name] = {
                                                                                    "range_name": range_name, 
                                                                                    "property_uri": prop_uri
                                                                                    }

                # Find object properties
                elif (prop, rdflib.RDF.type, rdflib.OWL.ObjectProperty) in rdf_graph:
                    if isinstance(range_uri, rdflib.URIRef):
                        # It is possible to have multiple ranges for an object property.
                        range_names = get_all_class_paths(rdf_graph, range_uri) # E.g., [Thing.Agent.Person.Musician, Thing.MusicArtist.Musician ...]
                    else:
                        range_names = ["Thing"]
                    prop_uri = str(prop)
                    obj_prop_chars = get_obj_prop_characteristics(rdf_graph=rdf_graph, obj_prop=prop)
                    res = {
                        "range_names": range_names, 
                        "characteristics": obj_prop_chars,
                        "property_uri": prop_uri,
                        "ids": [] # A list that contains the IDs of the objects that are linked to an instance via this property.
                        }
                    class_property_map[class_name]["object_properties"][property_name] = res
    class_property_map = dict(class_property_map)
    
    # Merge class properties of all classes with their superclasses.
    class_property_map = merge_class_properties(rdf_graph=rdf_graph, class_property_map=class_property_map)

    class_property_map = sort_class_property_map(class_property_map=class_property_map)

    return class_property_map

def sort_class_property_map(class_property_map:Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Sorts the class property map by class name and then by property name for
    each class.

    Args:
        class_property_map (Dict[str, Dict[str, str]]): The class property map to sort.
    """
    # Sort all the classes by name
    class_property_map = dict(sorted(class_property_map.items(), key=lambda item: item[0]))
    
    # Sort the properties of each class by name
    for class_name, properties in class_property_map.items():
        class_property_map[class_name]["object_properties"] = dict(sorted(properties["object_properties"].items(), key=lambda item: item[0]))
        class_property_map[class_name]["data_properties"] = dict(sorted(properties["data_properties"].items(), key=lambda item: item[0]))
    return class_property_map

def create_trimmed_class_property_mappings(class_property_map:Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """
    Creates a trimmed version of the class property mappings, which is
    essentially the mappings but with the URI associated with each property being 
    removed.

    Args:
        class_property_map (Dict[str, Dict[str, str]]): A mapping of classes to their properties 
                                                        and the datatype of those properties.
    """
    trimmed_class_property_mappings = {}
    for c_class in class_property_map.keys():
        c_class_obj_props = class_property_map[c_class]["object_properties"]
        c_class_data_props = class_property_map[c_class]["data_properties"]
        

        new_obj_props = {}
        for obj_prop_name, obj_prop_dict in c_class_obj_props.items():
            new_obj_props[obj_prop_name] = {
                                            "range_names": obj_prop_dict["range_names"],
                                            "characteristics": obj_prop_dict["characteristics"]
                                            }
        new_data_props = {}
        for data_prop_name, data_prop_dict in c_class_data_props.items():
            new_data_props[data_prop_name] = {
                                            "range_name": data_prop_dict["range_name"]
                                            }
        trimmed_class_property_mappings[c_class] = {
                                                    "object_properties": new_obj_props,
                                                    "data_properties": new_data_props
                                                    }
    return trimmed_class_property_mappings