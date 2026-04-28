from app.api.schemas.perfume import PerfumeCard, PerfumeWithRelevance
from app.core.entities.perfume import Perfume
from app.core.entities.perfume import PerfumeWithRelevance as DomainPerfumeWithRelevance


def _extract_notes(perfume: Perfume) -> tuple[list[str], list[str], list[str]]:
    top = [pn.note.name for pn in perfume.notes if pn.level.lower() == "top"][:5]
    middle = [pn.note.name for pn in perfume.notes if pn.level.lower() == "middle"][:5]
    base = [pn.note.name for pn in perfume.notes if pn.level.lower() == "base"][:5]
    return top, middle, base


def perfume_to_card(perfume: Perfume) -> PerfumeCard:
    top, middle, base = _extract_notes(perfume)
    return PerfumeCard(
        id=perfume.id,
        name=perfume.name,
        brand=perfume.brand,
        image_url=perfume.image_url,
        source_url=perfume.source_url,
        family=perfume.family,
        gender=perfume.gender,
        category=perfume.category,
        review_summary=perfume.review_summary,
        top_notes=top,
        middle_notes=middle,
        base_notes=base,
    )


def perfume_with_relevance_to_response(item: DomainPerfumeWithRelevance) -> PerfumeWithRelevance:
    top, middle, base = _extract_notes(item.perfume)
    return PerfumeWithRelevance(
        id=item.perfume.id,
        name=item.perfume.name,
        brand=item.perfume.brand,
        image_url=item.perfume.image_url,
        source_url=item.perfume.source_url,
        family=item.perfume.family,
        gender=item.perfume.gender,
        category=item.perfume.category,
        review_summary=item.perfume.review_summary,
        top_notes=top,
        middle_notes=middle,
        base_notes=base,
        relevance=item.relevance,
    )
