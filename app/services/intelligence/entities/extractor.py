"""Deterministic entity extraction and disambiguation service."""

import re


class EntityExtractor:
    """Extracts and normalizes named entities (person, organization, location, brand) from article text."""

    STOP_WORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
        "by", "from", "up", "about", "into", "over", "after", "its", "it", "this",
        "that", "new", "says", "said", "will", "would", "could", "should", "as", "is",
        "are", "was", "were", "has", "have", "had", "been", "news", "report", "update",
        "breaking", "exclusive", "first", "watch", "live", "amid", "under",
    }

    # Known high-precision entities
    KNOWN_ORGANIZATIONS = {
        "united nations": "organization", "un": "organization", "who": "organization",
        "nato": "organization", "eu": "organization", "european union": "organization",
        "imf": "organization", "world bank": "organization", "bbc": "organization",
        "reuters": "organization", "associated press": "organization", "cnn": "organization",
        "nasa": "organization", "fbi": "organization", "cia": "organization",
    }

    KNOWN_BRANDS = {
        "apple": "brand", "google": "brand", "microsoft": "brand", "amazon": "brand",
        "tesla": "brand", "meta": "brand", "nvidia": "brand", "openai": "brand",
        "samsung": "brand", "sony": "brand", "spacex": "brand",
    }

    KNOWN_LOCATIONS = {
        "united states": "country", "usa": "country", "uk": "country", "britain": "country",
        "nigeria": "country", "china": "country", "ukraine": "country", "russia": "country",
        "germany": "country", "france": "country", "japan": "country", "india": "country",
        "london": "location", "lagos": "location", "abuja": "location", "tokyo": "location",
        "paris": "location", "washington": "location", "new york": "location", "beijing": "location",
        "kyiv": "location", "berlin": "location",
    }

    @classmethod
    def normalize_name(cls, name: str) -> str:
        """Normalizes an entity name into canonical alphanumeric identifier."""
        clean = re.sub(r"[^a-zA-Z0-9\s]", "", name).strip().lower()
        return re.sub(r"\s+", "_", clean)

    @classmethod
    def extract_entities(cls, title: str, description: str = "") -> list[tuple[str, str, float]]:
        """Extracts entities from title and description.
        Returns: List of (name, entity_type, confidence)
        """
        combined = f"{title} {description}"
        results: dict[str, tuple[str, str, float]] = {}

        # 1. Match known organizations, brands, locations
        text_lower = combined.lower()

        for term, etype in cls.KNOWN_ORGANIZATIONS.items():
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text_lower):
                norm = cls.normalize_name(term)
                results[norm] = (term.title() if len(term) > 3 else term.upper(), etype, 0.95)

        for term, etype in cls.KNOWN_BRANDS.items():
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text_lower):
                norm = cls.normalize_name(term)
                results[norm] = (term.title(), etype, 0.95)

        for term, etype in cls.KNOWN_LOCATIONS.items():
            pattern = r"\b" + re.escape(term) + r"\b"
            if re.search(pattern, text_lower):
                norm = cls.normalize_name(term)
                results[norm] = (term.title() if len(term) > 3 else term.upper(), etype, 0.90)

        # 2. Extract capitalized title words / proper names
        words = title.split()
        i = 0
        while i < len(words):
            word = words[i].strip('",.:;!?()[]{}')
            if word and word[0].isupper() and word.lower() not in cls.STOP_WORDS and len(word) > 2:
                # Check for two-word or three-word proper nouns
                phrase = [word]
                j = i + 1
                while j < len(words):
                    next_word = words[j].strip('",.:;!?()[]{}')
                    if next_word and next_word[0].isupper() and next_word.lower() not in cls.STOP_WORDS:
                        phrase.append(next_word)
                        j += 1
                    else:
                        break

                entity_str = " ".join(phrase)
                norm = cls.normalize_name(entity_str)
                if norm and norm not in results:
                    # Determine type: if 2 words, often person or organization
                    etype = "person" if len(phrase) >= 2 else "organization"
                    results[norm] = (entity_str, etype, 0.75)
                i = j
            else:
                i += 1

        return list(results.values())
