import rdflib
from collections import defaultdict
from typing import Dict, Any
from music_history_ontology.rdf_reading.functions import convert_rdffile_to_graph, get_readable_name

def build_class_tree(rdf_file_path: str) -> Dict[str, Any]:
    """
    Builds a class tree based on the class hierarchy of the provided
    RDF file.
    
    Args:
        rdf_file_path (str): Path to the RDF file.
    """
    rdf_graph = convert_rdffile_to_graph(rdf_file_path)
    children_map = defaultdict(list)
    all_classes = set()

    # Track subclass relationships and collect all classes
    for subclass, superclass in rdf_graph.subject_objects(rdflib.RDFS.subClassOf):
        if isinstance(subclass, rdflib.URIRef) and isinstance(superclass, rdflib.URIRef):
            subclass_name = get_readable_name(subclass)
            superclass_name = get_readable_name(superclass)
            children_map[superclass_name].append(subclass_name)
            all_classes.update([subclass_name, superclass_name])

    # Collect any classes defined as owl:Class or rdfs:Class that are not subclasses
    for cls in rdf_graph.subjects(rdflib.RDF.type, rdflib.OWL.Class):
        if isinstance(cls, rdflib.URIRef):
            all_classes.add(get_readable_name(cls))
    for cls in rdf_graph.subjects(rdflib.RDF.type, rdflib.RDFS.Class):
        if isinstance(cls, rdflib.URIRef):
            all_classes.add(get_readable_name(cls))

    def insert_recursive(node):
        return {child: insert_recursive(child) for child in children_map.get(node, [])}

    # Roots: classes that are not subclasses of anything
    subclasses = {c for sublist in children_map.values() for c in sublist}
    roots = sorted(all_classes - subclasses)

    # Build the full tree
    tree = {root: insert_recursive(root) for root in roots}

    return tree