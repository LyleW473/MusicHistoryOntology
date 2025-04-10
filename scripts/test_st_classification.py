import set_path
from music_history_ontology.data_ingestion.wikipedia.functions import retrieve_first_wikipedia_page
from music_history_ontology.data_ingestion.wikipedia.llm import LLMTextGenerator

if __name__ == "__main__":
    search_query_to_class = {
        # Musicians/Composers
        "Mozart": "Musicians/Composers",
        "Freddie Mercury": "Musicians/Composers",
        "Beyoncé": "Musicians/Composers",
        "Hans Zimmer": "Musicians/Composers",

        # Instruments
        "Piano": "Instruments",
        "Theremin": "Instruments",
        "Sitar": "Instruments",
        "French horn": "Instruments",

        # Songs/Works/Compositions
        "Symphony No. 40": "Songs/Works/Compositions",
        "Bohemian Rhapsody": "Songs/Works/Compositions",
        "Clair de Lune": "Songs/Works/Compositions",
        "That's All Right": "Songs/Works/Compositions",

        # Albums
        "The Dark Side of the Moon": "Albums",
        "Thriller": "Albums",
        "Random Access Memories": "Albums",
        "Donda": "Albums",

        # Events
        "First jazz recording": "Events",
        "Beethoven's Ninth premiere": "Events",
        "Grammy Awards 2023": "Events",
        "Live Aid concert": "Events",

        # Places
        "Salzburg": "Places",
        "Abbey Road Studios": "Places",
        "Vienna": "Places",
        "Motown Museum": "Places",

        # Other
        "Billboard Hot 100": "Other",
        "Rock and Roll Hall of Fame": "Other",
        "Music theory": "Other",
        "Classical period": "Other"
    }

    llm = LLMTextGenerator(role="search_query_classification")
    num_correct = 0
    for search_query, expected_class in search_query_to_class.items():
        base_page_id, base_page = retrieve_first_wikipedia_page(search_term=search_query)

        context_text = base_page.summary
        json_answer = llm.execute(text=context_text, search_query=search_query)
        print(f"Search query: {search_query} | JSON Answer: {json_answer}")
        if json_answer["class"] == expected_class:
            num_correct += 1

    print(f"Total correct classifications: {num_correct}/{len(search_query_to_class)}")
    print(f"Accuracy: {num_correct / len(search_query_to_class) * 100:.5f}%")