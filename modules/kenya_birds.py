"""
modules/kenya_birds.py — Kenya bird species database.

NOTE: This module provides a curated species list for birds found at
      Nairobi National Park, Kenya's first national park, located just
      south of Nairobi. The park has over 500 recorded bird species across
      grassland savanna, acacia woodland, riverine forest, and wetland habitats.

WHY: Bird rarity is location-dependent. A Lilac-breasted Roller is common
     in Nairobi National Park but would be accidental in Oregon. This module
     gives the user a location-specific starting point for the RarityChecker.

DESIGN: Same interface as pnw_birds.py — generates a rarity YAML dict that
        can be loaded by RarityChecker or written to a file.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# NOTE: Nairobi National Park is at approximately 1.37°S, 36.86°E
# It's 117 km² of savanna grassland, acacia woodland, riverine forest
# along the Embakasi/Mbagathi River, and rocky gorges.
# Over 500 bird species recorded.

LOCATION_NAME = "Nairobi National Park, Kenya"
LOCATION_COORDS = {"lat": -1.37, "lon": 36.86}

SPECIES_DATA: list[dict[str, Any]] = [
    # --- Common savanna residents ---
    {
        "name": "Lilac-breasted Roller",
        "scientific_name": "Coracias caudatus",
        "rarity": "common",
        "notes": "Stunning multi-colored bird. Perches on acacia trees, often near roads.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "Superb Starling",
        "scientific_name": "Lamprotornis superbus",
        "rarity": "common",
        "notes": "Iridescent plumage. Bold at picnic sites and lodges.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "Helmeted Guineafowl",
        "scientific_name": "Numida meleagris",
        "rarity": "common",
        "notes": "Flocks walk through grassland. Often at park roadsides.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "Yellow-necked Spurfowl",
        "scientific_name": "Pternistis leucoscepus",
        "rarity": "common",
        "notes": "Common in dry bush and grassland. Often in pairs or small groups.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "Red-billed Hornbill",
        "scientific_name": "Tockus erythrorhynchus",
        "rarity": "common",
        "notes": "Ground-feeding hornbill. Common in dry savanna.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "African Grey Hornbill",
        "scientific_name": "Tockus nasutus",
        "rarity": "common",
        "notes": "More arboreal than Red-billed. Acacia woodland.",
        "habitat": "acacia",
        "season": "year-round",
    },
    {
        "name": "White-bellied Go-away-bird",
        "scientific_name": "Criniferoides leucogaster",
        "rarity": "common",
        "notes": "Large grey turaco relative. Call sounds like 'go-away'.",
        "habitat": "acacia",
        "season": "year-round",
    },
    {
        "name": "African Sacred Ibis",
        "scientific_name": "Threskiornis aethiopicus",
        "rarity": "common",
        "notes": "Wetland areas and grassland. Nomadic flocks.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Hadada Ibis",
        "scientific_name": "Bostrychia hagedash",
        "rarity": "common",
        "notes": "Loud raucous call at dawn. Feeds on lawns and wetland margins.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Marabou Stork",
        "scientific_name": "Leptoptilos crumenifer",
        "rarity": "common",
        "notes": "Large scavenger. Often near carcasses or rubbish areas.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "Yellow-billed Oxpecker",
        "scientific_name": "Buphagus africanus",
        "rarity": "common",
        "notes": "Rides on large mammals, feeding on ticks. Often on rhinos and buffalo.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "Cattle Egret",
        "scientific_name": "Bubulcus ibis",
        "rarity": "common",
        "notes": "White heron following grazing animals for insects.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "African Jacana",
        "scientific_name": "Actophilornis africanus",
        "rarity": "common",
        "notes": "Lily-trotter with very long toes. Wetland pools and dams.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Blacksmith Plover",
        "scientific_name": "Vanellus armatus",
        "rarity": "common",
        "notes": "Black and white plover. Call sounds like a blacksmith's hammer.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Speckled Mousebird",
        "scientific_name": "Colius striatus",
        "rarity": "common",
        "notes": "Long-tailed, crested. Scrambles through bushes in small flocks.",
        "habitat": "acacia",
        "season": "year-round",
    },
    {
        "name": "Little Bee-eater",
        "scientific_name": "Merops pusillus",
        "rarity": "common",
        "notes": "Small green bee-eater. Perches low near water and clearings.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "White-fronted Bee-eater",
        "scientific_name": "Merops bullockoides",
        "rarity": "common",
        "notes": "Colonial nester in riverbanks. Colorful, aerial insectivore.",
        "habitat": "riverine",
        "season": "year-round",
    },
    {
        "name": "Red-cheeked Cordon-bleu",
        "scientific_name": "Uraeginthus bengalus",
        "rarity": "common",
        "notes": "Small waxbill. Blue body, red cheeks. At lodge bird feeders.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "Red-billed Firefinch",
        "scientific_name": "Lagonosticta senegala",
        "rarity": "common",
        "notes": "Small red finch. Gardens and savanna edges.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "African Silverbill",
        "scientific_name": "Euodice cantans",
        "rarity": "common",
        "notes": "Small brown finch with pale bill. Grassland and bush.",
        "habitat": "grassland",
        "season": "year-round",
    },

    # --- Uncommon / habitat specialists ---
    {
        "name": "Kori Bustard",
        "scientific_name": "Ardeotis kori",
        "rarity": "uncommon",
        "notes": "Heaviest flying bird in Africa. Open grassland, wary.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "White-bellied Bustard",
        "scientific_name": "Eupodotis senegalensis",
        "rarity": "uncommon",
        "notes": "Smaller bustard. Open grassland in pairs.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "Von der Decken's Hornbill",
        "scientific_name": "Tockus deckeni",
        "rarity": "uncommon",
        "notes": "Acacia savanna specialist. Male has two-tone bill.",
        "habitat": "acacia",
        "season": "year-round",
    },
    {
        "name": "Crowned Hornbill",
        "scientific_name": "Lophoceros alboterminatus",
        "rarity": "uncommon",
        "notes": "Riverine forest. More arboreal than other hornbills.",
        "habitat": "riverine",
        "season": "year-round",
    },
    {
        "name": "African Pygmy Kingfisher",
        "scientific_name": "Ispidina picta",
        "rarity": "uncommon",
        "notes": "Tiny, colorful kingfisher. Dense bush near water.",
        "habitat": "riverine",
        "season": "year-round",
    },
    {
        "name": "Malachite Kingfisher",
        "scientific_name": "Corythornis cristatus",
        "rarity": "uncommon",
        "notes": "Small blue and orange kingfisher. Reeds at wetland edges.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "African Hoopoe",
        "scientific_name": "Upupa africana",
        "rarity": "uncommon",
        "notes": "Distinctive fan-crested bird. Ground-foraging in open areas.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "Namaqua Dove",
        "scientific_name": "Oena capensis",
        "rarity": "uncommon",
        "notes": "Small dove with long tail. Dry savanna and bush.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "African Orange-bellied Parrot",
        "scientific_name": "Poicephalus rufiventris",
        "rarity": "uncommon",
        "notes": "Small parrot. Acacia woodland, feeds on pods and seeds.",
        "habitat": "acacia",
        "season": "year-round",
    },
    {
        "name": "Dideric Cuckoo",
        "scientific_name": "Chrysococcyx caprius",
        "rarity": "uncommon",
        "notes": "Brood parasite. Green-backed with yellow underparts. Calls 'dee-dee-deric'.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "Fischer's Lovebird",
        "scientific_name": "Agapornis fischeri",
        "rarity": "uncommon",
        "notes": "Small green and orange parrot. Flocks in acacia woodland.",
        "habitat": "acacia",
        "season": "year-round",
    },

    # --- Palearctic migrants (Oct-April) ---
    {
        "name": "European Roller",
        "scientific_name": "Coracias garrulus",
        "rarity": "uncommon",
        "notes": "Palearctic migrant. Present October to April. Perches on bushes.",
        "habitat": "savanna",
        "season": "winter_migrant",
    },
    {
        "name": "Steppe Eagle",
        "scientific_name": "Aquila nipalensis",
        "rarity": "uncommon",
        "notes": "Palearctic migrant. Soars over grassland Oct-March.",
        "habitat": "grassland",
        "season": "winter_migrant",
    },
    {
        "name": "Common Kestrel",
        "scientific_name": "Falco tinnunculus",
        "rarity": "uncommon",
        "notes": "Palearctic migrant. Hovers over grassland hunting rodents.",
        "habitat": "grassland",
        "season": "winter_migrant",
    },
    {
        "name": "European Bee-eater",
        "scientific_name": "Merops apiaster",
        "rarity": "uncommon",
        "notes": "Migrant flocks. Colorful, aerial hawking over savanna.",
        "habitat": "savanna",
        "season": "migrant",
    },

    # --- Rare / special sightings ---
    {
        "name": "Martial Eagle",
        "scientific_name": "Polemaetus bellicosus",
        "rarity": "rare",
        "notes": "Africa's largest eagle. Soars high, hunts small antelope and gamebirds.",
        "habitat": "savanna",
        "season": "year-round",
    },
    {
        "name": "African Crowned Eagle",
        "scientific_name": "Stephanoaetus coronatus",
        "rarity": "rare",
        "notes": "Forest eagle. Riverine forest canopy. Powerful hunter of monkeys.",
        "habitat": "riverine",
        "season": "year-round",
    },
    {
        "name": "African Fish Eagle",
        "scientific_name": "Haliaeetus vocifer",
        "rarity": "rare",
        "notes": "Iconic call. Perches near water, hunts fish and waterbirds.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Secretary Bird",
        "scientific_name": "Sagittarius serpentarius",
        "rarity": "rare",
        "notes": "Tall crane-like raptor. Stalks through tall grass hunting snakes.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "Saddle-billed Stork",
        "scientific_name": "Ephippiorhynchus senegalensis",
        "rarity": "rare",
        "notes": "Large, striking stork. Wetland areas, usually solitary or in pairs.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Grey Crowned Crane",
        "scientific_name": "Balearica regulorum",
        "rarity": "rare",
        "notes": "National bird of Uganda. Golden crest. Wetland grassland.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Hartlaub's Turaco",
        "scientific_name": "Tauraco hartlaubi",
        "rarity": "rare",
        "notes": "Forest canopy. Brilliant green and red wings in flight.",
        "habitat": "riverine",
        "season": "year-round",
    },
    {
        "name": "Narina Trogon",
        "scientific_name": "Apaloderma narina",
        "rarity": "rare",
        "notes": "Secretive forest bird. Riverine forest canopy.",
        "habitat": "riverine",
        "season": "year-round",
    },
    {
        "name": "African Pied Wagtail",
        "scientific_name": "Motacilla aguimp",
        "rarity": "rare",
        "notes": "Black and white wagtail. Rocky river edges and dams.",
        "habitat": "riverine",
        "season": "year-round",
    },
    {
        "name": "Ross's Turaco",
        "scientific_name": "Musophaga rossae",
        "rarity": "rare",
        "notes": "Vivid blue and red. Dense riverine forest. More common further west.",
        "habitat": "riverine",
        "season": "year-round",
    },

    # --- Very rare / vagrants ---
    {
        "name": "Shoebill",
        "scientific_name": "Balaeniceps rex",
        "rarity": "very_rare",
        "notes": "Enormous prehistoric-looking stork. Papyrus swamps. Rare vagrant to Nairobi area.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Denham's Bustard",
        "scientific_name": "Neotis denhami",
        "rarity": "very_rare",
        "notes": "Large bustard. Open grassland. Declining population.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "Jackson's Widowbird",
        "scientific_name": "Euplectes jacksoni",
        "rarity": "very_rare",
        "notes": "Highland grassland. Males have long tail in breeding season.",
        "habitat": "grassland",
        "season": "year-round",
    },
    {
        "name": "Abyssinian Ground Hornbill",
        "scientific_name": "Bucorvus abyssinicus",
        "rarity": "very_rare",
        "notes": "Large ground-dwelling hornbill. Very rare in Nairobi NP, more common further north.",
        "habitat": "grassland",
        "season": "year-round",
    },

    # --- Accidental ---
    {
        "name": "Madagascar Squacco Heron",
        "scientific_name": "Ardeola idae",
        "rarity": "accidental",
        "notes": "Extremely rare vagrant from Madagascar. Wetland only.",
        "habitat": "wetland",
        "season": "year-round",
    },
    {
        "name": "Egyptian Vulture",
        "scientific_name": "Neophron percnopterus",
        "rarity": "accidental",
        "notes": "Critically endangered. Very rare migrant, usually seen soaring.",
        "habitat": "savanna",
        "season": "migrant",
    },
]


def get_species_list() -> list[dict[str, Any]]:
    """Return the full Kenya species list."""
    return list(SPECIES_DATA)


def get_rarity_dict() -> dict[str, Any]:
    """Return species data as a dict keyed by lowercase species name."""
    result: dict[str, dict[str, Any]] = {}
    for entry in SPECIES_DATA:
        key = entry["name"].lower().strip()
        result[key] = {
            "name": entry["name"],
            "scientific_name": entry.get("scientific_name", ""),
            "rarity": entry.get("rarity", "common"),
            "notes": entry.get("notes", ""),
            "best_season": entry.get("season", ""),
            "habitat": entry.get("habitat", ""),
        }
    return result


def get_rarity_yaml() -> str:
    """Return the species data as a YAML string."""
    import yaml

    data = {
        "location": LOCATION_NAME,
        "coordinates": LOCATION_COORDS,
        "species": SPECIES_DATA,
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def write_rarity_file(path: str) -> None:
    """Write the rarity YAML to a file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(get_rarity_yaml())
    logger.info("Wrote Kenya rarity file with %d species to %s", len(SPECIES_DATA), path)


def get_species_by_habitat(habitat: str) -> list[dict[str, Any]]:
    """Filter species by habitat type."""
    return [s for s in SPECIES_DATA if s.get("habitat") == habitat]


def get_species_by_season(season: str) -> list[dict[str, Any]]:
    """Filter species by season."""
    return [s for s in SPECIES_DATA if season.lower() in s.get("season", "").lower()]


def get_species_by_rarity(rarity: str) -> list[dict[str, Any]]:
    """Filter species by rarity level."""
    return [s for s in SPECIES_DATA if s.get("rarity") == rarity.lower()]


def get_stats() -> dict[str, Any]:
    """Return summary statistics about the species database."""
    rarity_counts: dict[str, int] = {}
    habitat_counts: dict[str, int] = {}
    season_counts: dict[str, int] = {}

    for s in SPECIES_DATA:
        r = s.get("rarity", "common")
        rarity_counts[r] = rarity_counts.get(r, 0) + 1
        h = s.get("habitat", "unknown")
        habitat_counts[h] = habitat_counts.get(h, 0) + 1
        season = s.get("season", "year-round")
        season_counts[season] = season_counts.get(season, 0) + 1

    return {
        "total_species": len(SPECIES_DATA),
        "location": LOCATION_NAME,
        "rarity_breakdown": rarity_counts,
        "habitat_breakdown": habitat_counts,
        "season_breakdown": season_counts,
    }


__all__ = [
    "LOCATION_NAME",
    "LOCATION_COORDS",
    "SPECIES_DATA",
    "get_species_list",
    "get_rarity_dict",
    "get_rarity_yaml",
    "write_rarity_file",
    "get_species_by_habitat",
    "get_species_by_season",
    "get_species_by_rarity",
    "get_stats",
]