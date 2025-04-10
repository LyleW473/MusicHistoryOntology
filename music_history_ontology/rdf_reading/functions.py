import rdflib
from typing import List, Union

def get_readable_name(cls:rdflib.URIRef) -> str:
    """
    Converts a URIRef to a readable string.
    e.g., http://example.com/ontology#ClassName -> ClassName
    Args:
        cls (rdflib.URIRef): The URIRef to convert.
    """
    cls_str = str(cls)
    if "#" in cls_str:
        cls_str = cls_str.split("#")[-1]
    else:
        cls_str = cls_str.split("/")[-1]
    return cls_str

def convert_rdffile_to_graph(rdf_file_path:str) -> rdflib.Graph:
    """
    Converts the RDF file to a graph object.
    
    Args:
        rdf_file_path (str): Path to the RDF file.
    """
    graph = rdflib.Graph()
    graph.parse(rdf_file_path)
    return graph

def get_all_class_paths(rdf_graph: rdflib.Graph, cls: rdflib.URIRef, visited:Union[None, set[rdflib.URIRef]]=None) -> List[str]:
    """
    Recursively collects all possible full inheritance paths for a class,
    e.g., Thing.Agent.Person.Musician and Thing.MusicArtist.Musician

    Args:
        rdf_graph (rdflib.Graph): The graph object for the ontology.
        cls: The URI to find the full path for.
    """
    if visited is None:
        visited = set()

    # Check if the class is already visited to avoid infinite recursion
    if not isinstance(cls, rdflib.URIRef) or cls in visited:
        return []

    visited.add(cls)
    readable_cls = get_readable_name(cls)

    superclasses = [
                superclass for superclass in rdf_graph.objects(cls, rdflib.RDFS.subClassOf)
                if isinstance(superclass, rdflib.URIRef)
                ]

    if not superclasses:
        if readable_cls == "Thing":
            return ["Thing"]
        # If the class is not Thing and has no superclasses, return its own path.
        return [f"Thing.{readable_cls}"]

    # Recurse on all valid superclasses and collect all paths
    all_paths = []
    for superclass in superclasses:
        super_paths = get_all_class_paths(rdf_graph, superclass, visited.copy())
        for super_path in super_paths:
            all_paths.append(f"{super_path}.{readable_cls}")
    return all_paths

def is_declared_class(rdf_graph:rdflib.Graph, uri:str) -> bool:
    """
    Returns a boolean representing whether the URI is a declared class in
    the RDF graph.

    Args:
        rdf_graph (rdflib.Graph): The graph object for the ontology.
        uri (str): The URI to check.
    """
    return (
            (uri, rdflib.RDF.type, rdflib.OWL.Class) in rdf_graph or
            (uri, rdflib.RDF.type, rdflib.RDFS.Class) in rdf_graph
            )