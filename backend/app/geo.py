import math
import re
import unicodedata

GAZETTEER: dict[str, tuple[float, float]] = {
    "berlin": (52.5200, 13.4050),
    "berlin mitte": (52.5200, 13.4050),
    "berlin kreuzberg": (52.4980, 13.4030),
    "berlin friedrichshain": (52.5155, 13.4540),
    "berlin prenzlauer berg": (52.5390, 13.4240),
    "berlin charlottenburg": (52.5160, 13.3040),
    "berlin wilmersdorf": (52.4870, 13.3190),
    "berlin neukoelln": (52.4750, 13.4410),
    "berlin schoeneberg": (52.4820, 13.3550),
    "berlin wedding": (52.5500, 13.3600),
    "berlin moabit": (52.5300, 13.3400),
    "berlin tempelhof": (52.4670, 13.3850),
    "berlin steglitz": (52.4560, 13.3320),
    "berlin spandau": (52.5350, 13.2000),
    "berlin lichtenberg": (52.5150, 13.4980),
    "berlin treptow": (52.4930, 13.4570),
    "berlin koepenick": (52.4450, 13.5750),
    "berlin adlershof": (52.4310, 13.5410),
    "berlin pankow": (52.5690, 13.4020),
    "berlin reinickendorf": (52.5800, 13.3350),
    "berlin marzahn": (52.5450, 13.5670),
    "berlin zehlendorf": (52.4340, 13.2590),
    "berlin kaulsdorf": (52.5120, 13.5870),
    "berlin britz": (52.4490, 13.4400),
    "potsdam": (52.3906, 13.0645),
    "potsdam babelsberg": (52.3920, 13.0930),
    "babelsberg": (52.3920, 13.0930),
    "potsdam golm": (52.4090, 12.9680),
    "golm": (52.4090, 12.9680),
    "griebnitzsee": (52.3936, 13.1280),
    "werder havel": (52.3780, 12.9340),
    "werder": (52.3780, 12.9340),
    "teltow": (52.4020, 13.2740),
    "kleinmachnow": (52.4080, 13.2210),
    "stahnsdorf": (52.3850, 13.2170),
    "michendorf": (52.3080, 13.0280),
    "beelitz": (52.2350, 12.9700),
    "caputh": (52.3480, 13.0130),
    "falkensee": (52.5600, 13.0900),
    "ludwigsfelde": (52.3010, 13.2540),
    "wildau": (52.3200, 13.6400),
    "koenigs wusterhausen": (52.2960, 13.6230),
    "oranienburg": (52.7550, 13.2360),
    "bernau": (52.6790, 13.5870),
    "hennigsdorf": (52.6360, 13.2020),
    "brandenburg an der havel": (52.4125, 12.5316),
    "frankfurt oder": (52.3410, 14.5490),
    "cottbus": (51.7560, 14.3330),
    "eberswalde": (52.8340, 13.8180),
    "wittenberge": (52.9950, 11.7500),
    "hamburg": (53.5511, 9.9937),
    "muenchen": (48.1351, 11.5820),
    "koeln": (50.9375, 6.9603),
    "frankfurt am main": (50.1109, 8.6821),
    "leipzig": (51.3397, 12.3731),
    "dresden": (51.0504, 13.7373),
    "stuttgart": (48.7758, 9.1829),
    "duesseldorf": (51.2277, 6.7735),
    "hannover": (52.3759, 9.7320),
    "nuernberg": (49.4521, 11.0767),
    "bremen": (53.0793, 8.8017),
    "karlsruhe": (49.0069, 8.4037),
    "heidelberg": (49.3988, 8.6724),
    "muenster": (51.9607, 7.6261),
    "jena": (50.9271, 11.5892),
    "magdeburg": (52.1205, 11.6276),
    "rostock": (54.0924, 12.0991),
    "halle saale": (51.4825, 11.9705),
    "erfurt": (50.9848, 11.0299),
    "aachen": (50.7753, 6.0839),
    "bonn": (50.7374, 7.0982),
    "essen": (51.4556, 7.0116),
    "dortmund": (51.5136, 7.4653),
    "mannheim": (49.4875, 8.4660),
    "augsburg": (48.3705, 10.8978),
    "kiel": (54.3233, 10.1228),
    "wolfsburg": (52.4227, 10.7865),
    "ingolstadt": (48.7665, 11.4258),
    "tuebingen": (48.5216, 9.0576),
    "freiburg": (47.9990, 7.8421),
    "ulm": (48.4011, 9.9876),
    "regensburg": (49.0134, 12.1016),
    "braunschweig": (52.2689, 10.5268),
    "bielefeld": (52.0302, 8.5325),
    "wiesbaden": (50.0782, 8.2398),
    "darmstadt": (49.8728, 8.6512),
    "kassel": (51.3127, 9.4797),
    "osnabrueck": (52.2799, 8.0472),
    "paderborn": (51.7189, 8.7575),
    "luebeck": (53.8655, 10.6866),
    "chemnitz": (50.8278, 12.9214),
    "saarbruecken": (49.2402, 6.9969),
    "mainz": (49.9929, 8.2473),
    "konstanz": (47.6603, 9.1758),
    "wuerzburg": (49.7913, 9.9534),
}

UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
NOISE_TOKENS = {"deutschland", "germany", "de", "bei", "raum", "kreis", "landkreis", "am", "an", "der", "im"}
REMOTE_HINTS = {"remote", "homeoffice", "home office", "hybrid", "ortsunabhaengig"}
NATIONWIDE_HINTS = {"deutschlandweit", "bundesweit", "an allen standorten", "standortuebergreifend",
                    "nationwide", "vor ort in deiner naehe", "wunschfiliale"}


def normalize(value: str) -> str:
    text = (value or "").lower().strip()
    for source, target in UMLAUTS.items():
        text = text.replace(source, target)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    tokens = [t for t in text.split() if t and t not in NOISE_TOKENS]
    return " ".join(tokens)


def is_remote(value: str) -> bool:
    text = normalize(value)
    return any(normalize(hint) in text for hint in REMOTE_HINTS)


NORMALIZED_PLACES = {normalize(name): coords for name, coords in GAZETTEER.items()}
AMBIGUOUS_PLACES = {
    "frankfurt": ("frankfurt am main", "frankfurt oder"),
    "halle": ("halle saale",),
}
MAX_PLACE_WORDS = max(len(name.split()) for name in NORMALIZED_PLACES)


def is_nationwide(value: str) -> bool:
    text = normalize(value)
    return any(normalize(hint) in text for hint in NATIONWIDE_HINTS)


def find_places(value: str) -> list[tuple[str, tuple[float, float]]]:
    tokens = normalize(value).split()
    used = [False] * len(tokens)
    found: list[tuple[str, tuple[float, float]]] = []

    for size in range(min(MAX_PLACE_WORDS, len(tokens)), 0, -1):
        for start in range(len(tokens) - size + 1):
            if any(used[start : start + size]):
                continue
            candidate = " ".join(tokens[start : start + size])
            if candidate in NORMALIZED_PLACES:
                matches = [(candidate, NORMALIZED_PLACES[candidate])]
            elif candidate in AMBIGUOUS_PLACES:
                matches = [(candidate, NORMALIZED_PLACES[normalize(name)])
                           for name in AMBIGUOUS_PLACES[candidate]]
            else:
                continue
            for index in range(start, start + size):
                used[index] = True
            found.extend(matches)
    return found


def nearest_place(origin: tuple[float, float], value: str) -> tuple[float, str] | None:
    places = find_places(value)
    if not places:
        return None
    name, coords = min(places, key=lambda item: haversine_km(origin, item[1]))
    return haversine_km(origin, coords), name


def geocode(value: str) -> tuple[float, float] | None:
    key = normalize(value)
    if not key:
        return None
    if key in NORMALIZED_PLACES:
        return NORMALIZED_PLACES[key]

    places = find_places(value)
    if places:
        return max(places, key=lambda item: len(item[0]))[1]

    prefix_matches = [
        (name, coords) for name, coords in NORMALIZED_PLACES.items()
        if name.startswith(key + " ") or key.startswith(name + " ")
    ]
    if prefix_matches:
        return min(prefix_matches, key=lambda item: (-len(item[0]), item[0]))[1]
    return None


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    radius = 6371.0088
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def distance_between(origin: str, destination: str) -> float | None:
    a, b = geocode(origin), geocode(destination)
    if not a or not b:
        return None
    return haversine_km(a, b)
