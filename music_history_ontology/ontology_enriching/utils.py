import rdflib

def convert_data_prop_value(data_property_datatype:str, data_property_value:str) -> rdflib.Literal:
    """
    Converts the data property value to the correct datatype.
    
    Args:
        data_property_datatype (str): The datatype of the data property.
        data_property_value (str): The value of the data property.
    """

    data_property_datatype = data_property_datatype.lower()
    try:
        if data_property_datatype in ["string", "literal"]:
            return rdflib.Literal(data_property_value, datatype=rdflib.XSD.string)
        elif data_property_datatype == "integer":
            return rdflib.Literal(int(data_property_value), datatype=rdflib.XSD.integer)
        elif data_property_datatype == "float":
            return rdflib.Literal(float(data_property_value), datatype=rdflib.XSD.float)
        elif data_property_datatype == "double":
            return rdflib.Literal(float(data_property_value), datatype=rdflib.XSD.double)
        elif data_property_datatype == "boolean":
            val = str(data_property_value).lower() in ["true", "1", "yes"]
            return rdflib.Literal(val, datatype=rdflib.XSD.boolean)
        elif data_property_datatype == "datetime":
            return rdflib.Literal(data_property_value, datatype=rdflib.XSD.dateTime)
        elif data_property_datatype == "date":
            return rdflib.Literal(data_property_value, datatype=rdflib.XSD.date)
        elif data_property_datatype == "time":
            return rdflib.Literal(data_property_value, datatype=rdflib.XSD.time)
        else:
            # Treat as string if the datatype is not recognised
            return rdflib.Literal(data_property_value, datatype=rdflib.XSD.string)
    except Exception as e:
        print(f"Failed to convert {data_property_value} to {data_property_datatype}: {e}")
        return None