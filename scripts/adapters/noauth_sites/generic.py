from __future__ import annotations

from urllib.parse import urlparse

from .base import BaseNoAuthAdapter


class WordPressAdapter(BaseNoAuthAdapter):
    name = "wordpress"
    templates = ["/?s={query}"]

    def match(self, url: str, route: dict) -> bool:
        hay = f"{url} {route.get('source_name','')}".lower()
        return "wordpress" in hay or "wp-content" in hay


class DrupalAdapter(BaseNoAuthAdapter):
    name = "drupal"
    templates = ["/search/node/{query}", "/search?search={query}"]

    def match(self, url: str, route: dict) -> bool:
        hay = f"{url} {route.get('source_name','')}".lower()
        return "drupal" in hay or "/node/" in hay


class OmekaAdapter(BaseNoAuthAdapter):
    name = "omeka"
    templates = ["/items/browse?search={query}"]

    def match(self, url: str, route: dict) -> bool:
        return "omeka" in f"{url} {route.get('source_name','')}".lower()


class AtoMAdapter(BaseNoAuthAdapter):
    name = "atom"
    templates = ["/index.php/informationobject/browse?topLod=0&query={query}", "/index.php/index.php/informationobject/browse?query={query}"]

    def match(self, url: str, route: dict) -> bool:
        hay = f"{url} {route.get('source_name','')}".lower()
        return "atom" in hay or "informationobject" in hay or "archivescollection" in hay


class GenericCatalogueAdapter(BaseNoAuthAdapter):
    name = "generic_catalogue"
    templates = ["/search?q={query}", "/search?query={query}", "/catalogue/search?search={query}", "/search?keywords={query}"]

    def match(self, url: str, route: dict) -> bool:
        return str(route.get("route_family") or "") in {"state_library_catalogue", "state_archive_catalogue", "national_library_catalogue", "public_collection"}


class GenericCouncilSearchAdapter(BaseNoAuthAdapter):
    name = "generic_council"
    templates = ["/search?query={query}", "/search?queries_keywords_query={query}", "/search?q={query}"]

    def match(self, url: str, route: dict) -> bool:
        return str(route.get("route_family") or "") in {"council_local_studies", "public_history_site"}


class GenericMuseumCollectionAdapter(BaseNoAuthAdapter):
    name = "generic_museum"
    templates = ["/search?query={query}", "/collection/search?query={query}", "/objects?search={query}"]

    def match(self, url: str, route: dict) -> bool:
        return str(route.get("route_family") or "") == "museum_heritage_page"


class GenericHistoricalSocietyAdapter(BaseNoAuthAdapter):
    name = "generic_historical_society"
    templates = ["/?s={query}", "/search?query={query}", "/search?q={query}"]

    def match(self, url: str, route: dict) -> bool:
        return str(route.get("route_family") or "") in {"historical_society", "local_history_serial"}


class GenericPDFIndexAdapter(BaseNoAuthAdapter):
    name = "generic_pdf_index"
    templates = ["/?s={query}", "/search?query={query}", "/search?q={query}"]

    def match(self, url: str, route: dict) -> bool:
        hay = f"{url} {route.get('source_name','')} {route.get('route_family','')}".lower()
        return any(token in hay for token in ["newsletter", "journal", "bulletin", "local_history_serial", "historical"])


ADAPTERS = [
    WordPressAdapter(),
    DrupalAdapter(),
    OmekaAdapter(),
    AtoMAdapter(),
    GenericCatalogueAdapter(),
    GenericCouncilSearchAdapter(),
    GenericMuseumCollectionAdapter(),
    GenericHistoricalSocietyAdapter(),
    GenericPDFIndexAdapter(),
]


def matching_adapters(url: str, route: dict):
    matched = [adapter for adapter in ADAPTERS if adapter.match(url, route)]
    return matched or [GenericCatalogueAdapter()]
