"""Similarity, threshold, and filter node handlers."""

from __future__ import annotations

from src.app.core.matching import _normalize_album
from src.app.core.models import TrackMetadata
from src.app.core.nodes.base import NodeHandlerBase, NodeInputs, NodeOutputs
from src.app.core.nodes.registry import register_node


@register_node("similarity")
class SimilarityNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        a = str(inputs.get("a", inputs.get("in", "")))
        b = str(inputs.get("b", self._config.get("value", "")))
        algorithm = self._config.get("algorithm", "jaccard")

        a_norm = a.lower().strip()
        b_norm = b.lower().strip()

        if algorithm == "exact":
            return {"out": 1.0 if a_norm == b_norm else 0.0}

        if algorithm == "substring":
            return {"out": 1.0 if a_norm in b_norm or b_norm in a_norm else 0.0}

        if algorithm == "jaccard":
            if not a_norm or not b_norm:
                return {"out": 0.0}
            tokens_a = set(a_norm.split())
            tokens_b = set(b_norm.split())
            intersection = tokens_a & tokens_b
            union = tokens_a | tokens_b
            return {"out": len(intersection) / len(union) if union else 0.0}

        if algorithm == "token_sort":
            if not a_norm or not b_norm:
                return {"out": 0.0}
            tokens_a = sorted(a_norm.split())
            tokens_b = sorted(b_norm.split())
            from difflib import SequenceMatcher

            sm = SequenceMatcher(None, tokens_a, tokens_b)
            return {"out": sm.ratio()}

        return {"out": 0.0}


@register_node("threshold")
class ThresholdNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        value = inputs.get("in", 0)
        threshold = self._config.get("threshold", 0.75)
        try:
            passed = float(value) >= threshold
        except ValueError, TypeError:
            passed = False
        return {"out": value if passed else None}


@register_node("filter")
class FilterNode(NodeHandlerBase):
    async def execute(self, track: TrackMetadata, inputs: NodeInputs) -> NodeOutputs:
        candidates = inputs.get("candidates", inputs.get("in", []))
        field = self._config.get("field", "artist_name")
        threshold = self._config.get("threshold", 0.6)
        reference = inputs.get("reference")

        if not isinstance(candidates, list):
            return {"out": []}

        if reference is None:
            reference = getattr(track, field, "") or ""
        ref_str = str(reference) if reference is not None else ""
        if not ref_str:
            return {"out": candidates}

        if field == "album_name":
            ref_norm = _normalize_album(ref_str)
            filtered = [
                c for c in candidates if _normalize_album(c.get("album_name", "")) == ref_norm
            ]
            return {"out": filtered}

        ref_norm = ref_str.lower().strip()
        filtered = []
        for c in candidates:
            val = str(c.get(field, ""))
            if not val:
                continue
            v_norm = val.lower().strip()
            sim = 0.0
            if v_norm == ref_norm:
                sim = 1.0
            elif v_norm in ref_norm or ref_norm in v_norm:
                sim = 0.85
            else:
                ref_tokens = set(ref_norm.split())
                val_tokens = set(v_norm.split())
                if ref_tokens and val_tokens:
                    sim = len(ref_tokens & val_tokens) / len(ref_tokens | val_tokens)
            if sim >= threshold:
                filtered.append(c)

        return {"out": filtered}
