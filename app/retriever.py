import json
import math
import re
from collections import Counter
from pathlib import Path


class Retriever:
    def __init__(self, data_path: str = "data/pages.json"):
        self.records = []
        path = Path(data_path)
        if path.exists():
            self.records = json.loads(path.read_text(encoding="utf-8"))

        self.chunks = []
        for record_index, record in enumerate(self.records):
            words = record["text"].split()
            step = 120
            size = 260
            if len(words) <= size:
                spans = [words]
            else:
                spans = [words[start:start + size] for start in range(0, len(words), step) if words[start:start + size]]
            for chunk_index, span in enumerate(spans):
                chunk = dict(record)
                chunk["chunk_id"] = f"{record_index}-{chunk_index}"
                chunk["text"] = " ".join(span)
                self.chunks.append(chunk)

        tokenized = [self._tokens(f"{c.get('title', '')} {c['category']} {c['text']}") for c in self.chunks]
        document_frequency = Counter()
        for tokens in tokenized:
            document_frequency.update(set(tokens))
        count = len(tokenized)
        self.idf = {
            term: math.log((count + 1) / (frequency + 1)) + 1
            for term, frequency in document_frequency.items()
        }
        self.vectors = []
        for tokens in tokenized:
            counts = Counter(tokens)
            vector = {term: frequency * self.idf.get(term, 1) for term, frequency in counts.items()}
            norm = math.sqrt(sum(value * value for value in vector.values()))
            self.vectors.append((vector, norm))

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[\w]+(?:-[\w]+)*", text.lower(), flags=re.UNICODE)

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        if len(a) < len(b):
            a, b = b, a
        previous = list(range(len(b) + 1))
        for i, char_a in enumerate(a, 1):
            current = [i]
            for j, char_b in enumerate(b, 1):
                current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (char_a != char_b)))
            previous = current
        return previous[-1]

    def normalize_query(self, query: str) -> str:
        aliases = {
            "darglobal": "DarGlobal", "dar global": "DarGlobal", "darglobel": "DarGlobal",
            "wasalt": "Wasalt", "wassalt": "Wasalt", "wasall": "Wasalt",
            "realestate": "real estate", "restate": "real estate", "restat": "real estate",
            "propery": "property", "prperty": "property", "appartment": "apartment",
            "apartmnt": "apartment", "vila": "villa", "operting": "operating",
            "operte": "operate", "oprate": "operate", "operateing": "operating",
            "developes": "develops", "develper": "developer",
        }
        lower = query.strip().lower()
        for misspelled, canonical in sorted(aliases.items(), key=lambda item: -len(item[0])):
            lower = re.sub(rf"\b{re.escape(misspelled)}\b", canonical.lower(), lower)

        vocabulary = {
            "darglobal", "wasalt", "property", "properties", "real", "estate", "luxury",
            "residence", "residences", "villa", "villas", "apartment", "apartments",
            "dubai", "riyadh", "saudi", "qatar", "oman", "jeddah", "location", "develop",
            "developer", "investment", "rent", "sale", "price", "availability", "where",
        }
        words = []
        for word in re.findall(r"[\w]+(?:-[\w]+)*", lower, flags=re.UNICODE):
            if len(word) < 4 or word in vocabulary:
                words.append(word)
                continue
            candidates = [(distance, candidate) for candidate in vocabulary
                          if abs(len(candidate) - len(word)) <= 2
                          for distance in [self._levenshtein(word, candidate)]
                          if distance <= 1]
            words.append(min(candidates)[1] if candidates else word)
        return " ".join(words)

    def resolve_context(self, query: str, history: list[dict[str, str]]) -> str:
        normalized = self.normalize_query(query)
        user_turns = [item for item in history[-6:] if item.get("role") == "user"]
        if not normalized or not user_turns:
            return normalized

        lower = normalized.lower()
        if not any(company in lower for company in ("darglobal", "wasalt")):
            previous_text = " ".join(turn.get("content", "") for turn in user_turns[-3:]).lower()
            if "darglobal" in previous_text:
                normalized = f"DarGlobal {normalized}"
            elif "wasalt" in previous_text:
                normalized = f"Wasalt {normalized}"

        if any(pronoun in lower.split() for pronoun in ("it", "they", "them", "that", "this", "their", "he", "she")):
            normalized = f"{user_turns[-1].get('content', '')} {normalized}".strip()
        return normalized

    def search(self, query: str, k: int = 8) -> list[dict]:
        query_terms = Counter(self._tokens(query))
        query_vector = {
            term: frequency * self.idf.get(term, 1)
            for term, frequency in query_terms.items()
        }
        query_norm = math.sqrt(sum(value * value for value in query_vector.values()))
        scores = []

        query_tokens = set(query_terms)
        for index, (vector, norm) in enumerate(self.vectors):
            dot_product = sum(value * vector.get(term, 0) for term, value in query_vector.items())
            lexical = dot_product / (query_norm * norm) if query_norm and norm else 0

            chunk = self.chunks[index]
            chunk_tokens = set(self._tokens(chunk["text"]))
            coverage = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)

            query_lower = query.lower()
            source_boost = 0.12 if (
                ("wasalt" in query_lower and chunk["source"] == "Wasalt")
                or ("darglobal" in query_lower and chunk["source"] == "DarGlobal")
            ) else 0
            category_boost = 0
            if "difference" in query_lower or "compare" in query_lower:
                if chunk.get("category") == "company":
                    category_boost += 0.12
            if any(word in query_lower for word in ("where", "location", "operate", "country", "city")):
                title_lower = chunk.get("title", "").lower()
                if "faq" in title_lower or "investor" in title_lower or chunk.get("category") == "company":
                    category_boost += 0.18
            scores.append((lexical * 0.75 + coverage * 0.20 + source_boost + category_boost, index))

        ranked = sorted(scores, reverse=True)
        results = []
        seen_sources: set[str] = set()
        seen_urls: set[str] = set()
        for score, index in ranked:
            if score <= 0:
                continue
            chunk = dict(self.chunks[index])
            if chunk["url"] in seen_urls:
                continue
            # Keep cross-source evidence when a question compares both companies.
            if len(seen_sources) >= 2 and chunk["source"] in seen_sources:
                continue
            chunk["score"] = float(score)
            chunk["text"] = chunk["text"][:2400]
            results.append(chunk)
            seen_urls.add(chunk["url"])
            seen_sources.add(chunk["source"])
            if len(results) >= k:
                break
        return results
