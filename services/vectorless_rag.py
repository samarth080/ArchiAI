"""Vectorless retrieval utilities for architectural planning knowledge.

This module intentionally avoids embeddings and uses metadata, structure,
and BM25-style lexical matching for grounded retrieval.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List

from rank_bm25 import BM25Okapi

from services.bylaw_loader import BylawRuleset

WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_]{1,}")


@dataclass
class KnowledgeChunk:
    chunk_id: str
    title: str
    text: str
    source: str
    region_id: str = "all"
    building_type: str = "all"
    tags: List[str] = field(default_factory=list)

    def to_dict(self, score: float) -> dict:
        return {
            "id": self.chunk_id,
            "title": self.title,
            "text": self.text,
            "source": self.source,
            "region_id": self.region_id,
            "building_type": self.building_type,
            "tags": self.tags,
            "score": round(float(score), 4),
        }


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def _default_chunks() -> List[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id="k_default_living_01",
            title="Living room near entry",
            text=(
                "Place the living room close to the primary entry for intuitive visitor access. "
                "Keep clear circulation from living to staircase and kitchen."
            ),
            source="built_in:residential_heuristics",
            tags=["residential", "circulation", "living_room"],
        ),
        KnowledgeChunk(
            chunk_id="k_default_kitchen_01",
            title="Kitchen adjacency",
            text=(
                "Kitchen should stay adjacent to dining or living for efficient movement. "
                "Ensure one exterior wall for ventilation and daylight where possible."
            ),
            source="built_in:residential_heuristics",
            tags=["residential", "kitchen", "ventilation"],
        ),
        KnowledgeChunk(
            chunk_id="k_default_stair_01",
            title="Stair placement",
            text=(
                "Staircases should be centrally reachable and not block primary circulation. "
                "Provide direct vertical connectivity from the entrance zone."
            ),
            source="built_in:residential_heuristics",
            tags=["circulation", "staircase"],
        ),
        KnowledgeChunk(
            chunk_id="k_default_bed_01",
            title="Bedroom privacy",
            text=(
                "Locate bedrooms away from noisy entry edges. "
                "Stack wet areas vertically to simplify plumbing and service shafts."
            ),
            source="built_in:residential_heuristics",
            tags=["bedroom", "privacy", "services"],
        ),
        KnowledgeChunk(
            chunk_id="k_default_vastu_01",
            title="Vastu as preference",
            text=(
                "Apply Vastu recommendations after legal constraints. "
                "When conflicts occur, keep bylaws and safety as higher priority."
            ),
            source="built_in:vastu_guidance",
            tags=["vastu", "tradeoff"],
        ),
    ]


def _parse_markdown_chunks(path: Path) -> List[KnowledgeChunk]:
    content = path.read_text(encoding="utf-8")
    sections = re.split(r"^#{1,3}\s+", content, flags=re.MULTILINE)

    # re.split removes headings; reconstruct pairs using findall.
    headings = re.findall(r"^#{1,3}\s+(.+)$", content, flags=re.MULTILINE)

    chunks: List[KnowledgeChunk] = []
    if not headings:
        text = content.strip()
        if text:
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{path.stem}_0",
                    title=path.stem.replace("_", " ").title(),
                    text=text,
                    source=str(path.name),
                )
            )
        return chunks

    body_sections = [section.strip() for section in sections[1:]]
    for idx, heading in enumerate(headings):
        if idx >= len(body_sections):
            continue
        text = body_sections[idx].strip()
        if not text:
            continue
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"{path.stem}_{idx}",
                title=heading.strip(),
                text=text,
                source=str(path.name),
            )
        )

    return chunks


def _parse_json_chunks(path: Path) -> List[KnowledgeChunk]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks: List[KnowledgeChunk] = []

    if isinstance(payload, dict):
        payload = payload.get("chunks", [])

    if not isinstance(payload, list):
        return chunks

    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            continue

        text = str(item.get("text", "")).strip()
        if not text:
            continue

        chunks.append(
            KnowledgeChunk(
                chunk_id=str(item.get("id", f"{path.stem}_{idx}")),
                title=str(item.get("title", path.stem)).strip(),
                text=text,
                source=str(item.get("source", path.name)),
                region_id=str(item.get("region_id", "all")).strip().lower() or "all",
                building_type=str(item.get("building_type", "all")).strip().lower() or "all",
                tags=[str(tag).strip().lower() for tag in item.get("tags", []) if str(tag).strip()],
            )
        )

    return chunks


def load_knowledge_chunks(knowledge_raw_dir: Path) -> List[KnowledgeChunk]:
    chunks: List[KnowledgeChunk] = []

    if knowledge_raw_dir.exists():
        for path in sorted(knowledge_raw_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() in {".md", ".txt"}:
                chunks.extend(_parse_markdown_chunks(path))
            elif path.suffix.lower() == ".json":
                chunks.extend(_parse_json_chunks(path))

    if not chunks:
        chunks.extend(_default_chunks())

    return chunks


def build_bylaw_context_chunks(bylaws: BylawRuleset) -> List[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            chunk_id=f"bylaw_{bylaws.region_id}_setbacks",
            title="Setback constraints",
            text=(
                f"Front setback {bylaws.setback_front_m}m, rear setback {bylaws.setback_rear_m}m, "
                f"side setback {bylaws.setback_side_m}m each side."
            ),
            source=f"bylaws:{bylaws.region_id}",
            region_id=bylaws.region_id,
            building_type=bylaws.building_type,
            tags=["bylaw", "setback"],
        ),
        KnowledgeChunk(
            chunk_id=f"bylaw_{bylaws.region_id}_far",
            title="FAR and floors",
            text=(
                f"Maximum FAR {bylaws.max_far}, maximum floors {bylaws.max_floors}, "
                f"maximum height {bylaws.max_height_m}m."
            ),
            source=f"bylaws:{bylaws.region_id}",
            region_id=bylaws.region_id,
            building_type=bylaws.building_type,
            tags=["bylaw", "far", "height"],
        ),
        KnowledgeChunk(
            chunk_id=f"bylaw_{bylaws.region_id}_coverage",
            title="Coverage and parking",
            text=(
                f"Maximum plot coverage {bylaws.max_plot_coverage_pct} percent. "
                f"Parking minimum {bylaws.parking.min_stalls_per_unit} per unit."
            ),
            source=f"bylaws:{bylaws.region_id}",
            region_id=bylaws.region_id,
            building_type=bylaws.building_type,
            tags=["bylaw", "coverage", "parking"],
        ),
    ]


class VectorlessKnowledgeRetriever:
    """Keyword and metadata based retriever with BM25 scoring."""

    def __init__(self, knowledge_raw_dir: Path):
        self.knowledge_raw_dir = knowledge_raw_dir
        self._chunks = load_knowledge_chunks(knowledge_raw_dir)

    def retrieve(
        self,
        query: str,
        region_id: str,
        building_type: str,
        top_k: int = 5,
        extra_chunks: Iterable[KnowledgeChunk] | None = None,
    ) -> List[dict]:
        chunks = list(self._chunks)
        if extra_chunks:
            chunks.extend(extra_chunks)

        if not chunks:
            return []

        corpus = [_tokenize(f"{chunk.title} {chunk.text} {' '.join(chunk.tags)}") for chunk in chunks]
        query_tokens = _tokenize(query)

        if not query_tokens:
            query_tokens = _tokenize(f"{region_id} {building_type} residence layout")

        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)

        ranked = []
        for chunk, score in zip(chunks, scores):
            boosted = float(score)

            if chunk.region_id in {"all", region_id}:
                boosted += 1.0
            if chunk.building_type in {"all", building_type}:
                boosted += 0.7
            if region_id in chunk.text.lower() or building_type in chunk.text.lower():
                boosted += 0.5

            ranked.append((boosted, chunk))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [chunk.to_dict(score) for score, chunk in ranked[: max(1, top_k)]]
