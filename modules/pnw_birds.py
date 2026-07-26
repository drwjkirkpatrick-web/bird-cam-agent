"""
modules/pnw_birds.py — Pacific Northwest bird species database.

NOTE: This module provides a curated species list for the Pacific Northwest,
      specifically birds found around McIver State Park in Clackamas County,
      Oregon. The park sits along the Clackamas River with mixed coniferous
      and deciduous forest, riparian corridors, and meadow habitat.

WHY: Rather than shipping a static database, this module provides a
     LOCATION-SPECIFIC rarity file that the user can load into the
     RarityChecker. It's a starting point — the user can add or modify
     species as they observe them.

DESIGN: This module generates a rarity YAML dict that can be loaded by
        RarityChecker.load_rarity_data() or written to a file with
        write_rarity_file(). The species list is factual — based on
        known bird populations in the Clackamas River corridor.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# NOTE: McIver State Park is at approximately 45.28°N, 122.37°W
# along the Clackamas River. Habitat types:
# - Riparian (river corridor, willow/alder/cottonwood)
# - Coniferous forest (Douglas fir, western red cedar, hemlock)
# - Deciduous understory (bigleaf maple, vine maple, sword fern)
# - Meadow and clearing (park facilities, trail edges)
# - Mixed hardwood-conifer transition

LOCATION_NAME = "McIver State Park, Clackamas County, Oregon"
LOCATION_COORDS = {"lat": 45.28, "lon": -122.37}

# NOTE: Species list is organized by habitat and includes year-round
# residents, summer breeders, winter visitors, and migrants.
# Rarity is relative to THIS specific location — a bird that's common
# in the Cascade foothills but rare at McIver specifically is marked
# accordingly.

SPECIES_DATA: list[dict[str, Any]] = [
    # --- Year-round residents (common) ---
    {
        "name": "American Robin",
        "scientific_name": "Turdus migratorius",
        "rarity": "common",
        "notes": "Year-round resident. Forages on lawns and meadow areas.",
        "habitat": "meadow",
        "season": "year-round",
    },
    {
        "name": "Black-capped Chickadee",
        "scientific_name": "Poecile atricapillus",
        "rarity": "common",
        "notes": "Year-round resident. Flocks in mixed-species foraging groups.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Chestnut-backed Chickadee",
        "scientific_name": "Poecile rufescens",
        "rarity": "common",
        "notes": "Year-round resident. Prefers coniferous forest.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Dark-eyed Junco",
        "scientific_name": "Junco hyemalis",
        "rarity": "common",
        "notes": "Year-round resident. Oregon variant common at feeders.",
        "habitat": "forest_edge",
        "season": "year-round",
    },
    {
        "name": "Steller's Jay",
        "scientific_name": "Cyanocitta stelleri",
        "rarity": "common",
        "notes": "Year-round resident. Bold at picnic areas and feeders.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Northern Flicker",
        "scientific_name": "Colaptes auratus",
        "rarity": "common",
        "notes": "Year-round resident. Red-shafted variant common in PNW.",
        "habitat": "forest_edge",
        "season": "year-round",
    },
    {
        "name": "Downy Woodpecker",
        "scientific_name": "Dryobates pubescens",
        "rarity": "common",
        "notes": "Year-round resident. Frequents deciduous trees along river.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Song Sparrow",
        "scientific_name": "Melospiza melodia",
        "rarity": "common",
        "notes": "Year-round resident. Dense riparian brush along Clackamas.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Spotted Towhee",
        "scientific_name": "Pipilo maculatus",
        "rarity": "common",
        "notes": "Year-round resident. Scrubby understory and forest edge.",
        "habitat": "forest_edge",
        "season": "year-round",
    },
    {
        "name": "American Crow",
        "scientific_name": "Corvus brachyrhynchos",
        "rarity": "common",
        "notes": "Year-round resident. Opportunistic at picnic areas.",
        "habitat": "meadow",
        "season": "year-round",
    },
    {
        "name": "European Starling",
        "scientific_name": "Sturnus vulgaris",
        "rarity": "common",
        "notes": "Year-round resident. Non-native. Common at feeders.",
        "habitat": "meadow",
        "season": "year-round",
    },
    {
        "name": "House Finch",
        "scientific_name": "Haemorhous mexicanus",
        "rarity": "common",
        "notes": "Year-round resident. Common at bird feeders.",
        "habitat": "forest_edge",
        "season": "year-round",
    },
    {
        "name": "Red-breasted Nuthatch",
        "scientific_name": "Sitta canadensis",
        "rarity": "common",
        "notes": "Year-round resident. Coniferous forest, climbs tree trunks.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Bushtit",
        "scientific_name": "Psaltriparus minimus",
        "rarity": "common",
        "notes": "Year-round resident. Flocks in mixed understory.",
        "habitat": "deciduous",
        "season": "year-round",
    },
    {
        "name": "Bewick's Wren",
        "scientific_name": "Thryomanes bewickii",
        "rarity": "common",
        "notes": "Year-round resident. Dense brush and riparian thickets.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Anna's Hummingbird",
        "scientific_name": "Calypte anna",
        "rarity": "common",
        "notes": "Year-round resident. Visits hummingbird feeders.",
        "habitat": "forest_edge",
        "season": "year-round",
    },

    # --- Uncommon visitors ---
    {
        "name": "Pileated Woodpecker",
        "scientific_name": "Dryocopus pileatus",
        "rarity": "uncommon",
        "notes": "Year-round resident. Large woodpecker, needs mature forest.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Hairy Woodpecker",
        "scientific_name": "Dryobates villosus",
        "rarity": "uncommon",
        "notes": "Year-round resident. Larger than Downy, prefers mature trees.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Western Scrub-Jay",
        "scientific_name": "Aphelocoma californica",
        "rarity": "uncommon",
        "notes": "Year-round resident. Expanding range in Willamette Valley.",
        "habitat": "meadow",
        "season": "year-round",
    },
    {
        "name": "Red-breasted Sapsucker",
        "scientific_name": "Sphyrapicus ruber",
        "rarity": "uncommon",
        "notes": "Year-round resident. Drills sap wells in willows and alders.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Pacific Wren",
        "scientific_name": "Troglodytes hiemalis",
        "rarity": "uncommon",
        "notes": "Year-round resident. Dense, damp forest understory near water.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Golden-crowned Kinglet",
        "scientific_name": "Regulus satrapa",
        "rarity": "uncommon",
        "notes": "Year-round resident. High canopy of coniferous forest.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Brown Creeper",
        "scientific_name": "Certhia americana",
        "rarity": "uncommon",
        "notes": "Year-round resident. Spirals up tree trunks in coniferous forest.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Western Tanager",
        "scientific_name": "Piranga ludoviciana",
        "rarity": "uncommon",
        "notes": "Summer breeder. Bright yellow body, red head. Coniferous canopy.",
        "habitat": "coniferous",
        "season": "summer",
    },
    {
        "name": "Black-throated Gray Warbler",
        "scientific_name": "Setophaga nigrescens",
        "rarity": "uncommon",
        "notes": "Summer breeder. Oak and mixed forest canopy.",
        "habitat": "deciduous",
        "season": "summer",
    },

    # --- Seasonal / Migrant visitors ---
    {
        "name": "Rufous Hummingbird",
        "scientific_name": "Selasphorus rufin",
        "rarity": "uncommon",
        "notes": "Spring/summer migrant. Arrives March-April, departs by August.",
        "habitat": "forest_edge",
        "season": "summer",
    },
    {
        "name": "Willow Flycatcher",
        "scientific_name": "Empidonax traillii",
        "rarity": "uncommon",
        "notes": "Summer breeder in riparian willow thickets along Clackamas River.",
        "habitat": "riparian",
        "season": "summer",
    },
    {
        "name": "Western Wood-Pewee",
        "scientific_name": "Contopus sordidulus",
        "rarity": "uncommon",
        "notes": "Summer breeder. Sallies from dead branches in forest openings.",
        "habitat": "forest_edge",
        "season": "summer",
    },
    {
        "name": "Townsend's Warbler",
        "scientific_name": "Setophaga townsendi",
        "rarity": "uncommon",
        "notes": "Migrant and some winter residents. Coniferous canopy.",
        "habitat": "coniferous",
        "season": "spring/fall",
    },
    {
        "name": "Wilson's Warbler",
        "scientific_name": "Cardellina pusilla",
        "rarity": "uncommon",
        "notes": "Summer breeder in riparian thickets. Bright yellow with black cap.",
        "habitat": "riparian",
        "season": "summer",
    },
    {
        "name": "Swainson's Thrush",
        "scientific_name": "Catharus ustulatus",
        "rarity": "uncommon",
        "notes": "Summer breeder. Veery-like song at dawn and dusk in riparian areas.",
        "habitat": "riparian",
        "season": "summer",
    },
    {
        "name": "Evening Grosbeak",
        "scientific_name": "Coccothraustes vespertinus",
        "rarity": "uncommon",
        "notes": "Irregular winter visitor. Flocks visit feeders in some years.",
        "habitat": "coniferous",
        "season": "winter",
    },
    {
        "name": "Pine Siskin",
        "scientific_name": "Spinus pinus",
        "rarity": "uncommon",
        "notes": "Irregular winter visitor. Flocks at feeders in irruption years.",
        "habitat": "coniferous",
        "season": "winter",
    },

    # --- Rare visitors to McIver specifically ---
    {
        "name": "Great Horned Owl",
        "scientific_name": "Bubo virginianus",
        "rarity": "rare",
        "notes": "Year-round resident in area but rarely seen at feeder during day.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Barred Owl",
        "scientific_name": "Strix varia",
        "rarity": "rare",
        "notes": "Year-round resident. More often heard than seen near river.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Northern Pygmy-Owl",
        "scientific_name": "Glaucidium gnoma",
        "rarity": "rare",
        "notes": "Year-round resident. Small diurnal owl, occasionally in forest edge.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Cooper's Hawk",
        "scientific_name": "Accipiter cooperii",
        "rarity": "rare",
        "notes": "Year-round resident. Occasionally hunts at bird feeders.",
        "habitat": "forest_edge",
        "season": "year-round",
    },
    {
        "name": "Sharp-shinned Hawk",
        "scientific_name": "Accipiter striatus",
        "rarity": "rare",
        "notes": "Migrant and winter visitor. Hunts small birds at feeders.",
        "habitat": "forest_edge",
        "season": "winter",
    },
    {
        "name": "Red-tailed Hawk",
        "scientific_name": "Buteo jamaicensis",
        "rarity": "rare",
        "notes": "Year-round resident in area. Soars over meadows, rarely at feeder.",
        "habitat": "meadow",
        "season": "year-round",
    },
    {
        "name": "Osprey",
        "scientific_name": "Pandion haliaetus",
        "rarity": "rare",
        "notes": "Summer resident. Nests along Clackamas River, fishes over water.",
        "habitat": "riparian",
        "season": "summer",
    },
    {
        "name": "Belted Kingfisher",
        "scientific_name": "Megaceryle alcyon",
        "rarity": "rare",
        "notes": "Year-round resident. Perches over Clackamas River, dives for fish.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "American Dipper",
        "scientific_name": "Cinclus mexicanus",
        "rarity": "rare",
        "notes": "Year-round resident. Walks underwater in Clackamas River rapids.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "White-headed Woodpecker",
        "scientific_name": "Dryobates albolarvatus",
        "rarity": "very_rare",
        "notes": "Rare visitor. Prefers mature ponderosa pine at higher elevations.",
        "habitat": "coniferous",
        "season": "year-round",
    },
    {
        "name": "Vaux's Swift",
        "scientific_name": "Chaetura vauxi",
        "rarity": "rare",
        "notes": "Summer breeder. Aerial forager over river at dusk.",
        "habitat": "riparian",
        "season": "summer",
    },
    {
        "name": "Cedar Waxwing",
        "scientific_name": "Bombycilla cedrorum",
        "rarity": "rare",
        "notes": "Irregular visitor. Flocks eat berries in riparian shrubs.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Varied Thrush",
        "scientific_name": "Ixoreus naevius",
        "rarity": "rare",
        "notes": "Winter visitor. Robin-like, prefers dark coniferous understory.",
        "habitat": "coniferous",
        "season": "winter",
    },
    {
        "name": "Snowy Owl",
        "scientific_name": "Bubo scandiacus",
        "rarity": "accidental",
        "notes": "Extremely rare irruptive visitor. Not expected at McIver but possible in major irruption years.",
        "habitat": "meadow",
        "season": "winter",
    },
    {
        "name": "Lewis's Woodpecker",
        "scientific_name": "Melanerpes lewis",
        "rarity": "very_rare",
        "notes": "Rare in western Oregon. Oak savanna specialist, occasional in Clackamas County.",
        "habitat": "deciduous",
        "season": "year-round",
    },
    {
        "name": "Hammond's Flycatcher",
        "scientific_name": "Empidonax hammondii",
        "rarity": "rare",
        "notes": "Migrant. Difficult to distinguish from other Empidonax flycatchers.",
        "habitat": "coniferous",
        "season": "spring/fall",
    },
    {
        "name": "Olive-sided Flycatcher",
        "scientific_name": "Contopus cooperi",
        "rarity": "rare",
        "notes": "Summer breeder at higher elevations. Perches on dead treetops.",
        "habitat": "coniferous",
        "season": "summer",
    },
    {
        "name": "Cassin's Vireo",
        "scientific_name": "Vireo cassinii",
        "rarity": "rare",
        "notes": "Summer breeder in mixed coniferous-deciduous forest.",
        "habitat": "coniferous",
        "season": "summer",
    },
    {
        "name": "Hutton's Vireo",
        "scientific_name": "Vireo huttoni",
        "rarity": "rare",
        "notes": "Year-round resident. Resembles Ruby-crowned Kinglet. Mixed flocks.",
        "habitat": "deciduous",
        "season": "year-round",
    },
    {
        "name": "Band-tailed Pigeon",
        "scientific_name": "Patagioenas fasciata",
        "rarity": "rare",
        "notes": "Summer visitor. Oregon's native pigeon, larger than Rock Pigeon.",
        "habitat": "coniferous",
        "season": "summer",
    },
    {
        "name": "Ruffed Grouse",
        "scientific_name": "Bonasa umbellus",
        "rarity": "rare",
        "notes": "Year-round resident. Forest floor, drumming in spring.",
        "habitat": "deciduous",
        "season": "year-round",
    },
    {
        "name": "Wild Turkey",
        "scientific_name": "Meleagris gallopavo",
        "rarity": "rare",
        "notes": "Year-round resident. Small flocks in meadow and forest edge.",
        "habitat": "meadow",
        "season": "year-round",
    },
    {
        "name": "Great Blue Heron",
        "scientific_name": "Ardea herodias",
        "rarity": "rare",
        "notes": "Year-round resident. Wades in Clackamas River shallows.",
        "habitat": "riparian",
        "season": "year-round",
    },
    {
        "name": "Common Merganser",
        "scientific_name": "Mergus merganser",
        "rarity": "rare",
        "notes": "Year-round resident. Dives for fish in Clackamas River.",
        "habitat": "riparian",
        "season": "year-round",
    },
]


def get_species_list() -> list[dict[str, Any]]:
    """Return the full PNW species list."""
    return list(SPECIES_DATA)


def get_rarity_dict() -> dict[str, Any]:
    """
    Return species data as a dict keyed by lowercase species name,
    compatible with RarityChecker._rarity_data format.
    """
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
    if logger:
        logger.info("Wrote PNW rarity file with %d species to %s", len(SPECIES_DATA), path)


def get_species_by_habitat(habitat: str) -> list[dict[str, Any]]:
    """Filter species by habitat type."""
    return [s for s in SPECIES_DATA if s.get("habitat") == habitat]


def get_species_by_season(season: str) -> list[dict[str, Any]]:
    """Filter species by season (year-round, summer, winter, spring/fall)."""
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