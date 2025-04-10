import set_path
import time
from music_history_ontology.data_ingestion.musicbrainz.conversion import convert_files

if __name__ == "__main__":
    start_time = time.perf_counter()
    data_folder = "generated_data/musicbrainz"
    output_folder = "generated_data/musicbrainz_converted"
    class_mappings_file = "rdf_components/class_property_mappings.json"

    convert_files(data_folder, output_folder, class_mappings_file)
    print(f"Conversion complete. Output saved to {output_folder}")
    print(f"Conversion time: {time.perf_counter() - start_time:.2f} seconds")