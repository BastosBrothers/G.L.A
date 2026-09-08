"""Búsqueda web usada por la herramienta buscar_documentacion_web."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


def now_local_str() -> str:
    try:
        tz = ZoneInfo("America/Caracas")
    except Exception:  # noqa: BLE001
        tz = None
    now = datetime.now(tz) if tz else datetime.now().astimezone()
    return now.strftime("%Y-%m-%d %H:%M %Z")


def search_web(query: str, *, max_results: int = 6) -> list[SearchHit]:
    """Busca en la web (DuckDuckGo). Sin API key."""
    query = (query or "").strip()
    if not query:
        return []

    try:
        # Paquete actual: ddgs (antes duckduckgo_search)
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore

        hits: list[SearchHit] = []
        with DDGS() as ddgs:
            for row in ddgs.text(query, max_results=max_results):
                hits.append(
                    SearchHit(
                        title=(row.get("title") or "").strip(),
                        url=(row.get("href") or row.get("link") or "").strip(),
                        snippet=(row.get("body") or row.get("snippet") or "").strip(),
                    )
                )
        return hits
    except Exception as exc:  # noqa: BLE001
        return [
            SearchHit(
                title="Error de búsqueda",
                url="",
                snippet=f"No se pudo investigar en vivo: {exc}",
            )
        ]


def format_research(query: str, hits: list[SearchHit]) -> str:
    stamp = now_local_str()
    lines = [
        f"Fecha/hora actual del sistema: **{stamp}**",
        f"Consulta de investigación: {query}",
        "",
        "Resultados (usa estos datos; cita URLs al final):",
    ]
    if not hits:
        lines.append("- (Sin resultados. Di que no encontraste fuentes y no inventes hechos recientes.)")
        return "\n".join(lines)

    for i, hit in enumerate(hits, start=1):
        lines.append(f"{i}. {hit.title}")
        if hit.url:
            lines.append(f"   URL: {hit.url}")
        if hit.snippet:
            lines.append(f"   Extracto: {hit.snippet}")
    return "\n".join(lines)


def build_research_block(user_query: str, *, max_results: int = 6) -> str:
    hits = search_web(user_query, max_results=max_results)
    return format_research(user_query, hits)
