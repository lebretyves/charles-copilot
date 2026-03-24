"""
CHARLES — RAG Engine (Retrieval-Augmented Generation).

Indexe la Knowledge Base clinique via embeddings (nomic-embed-text / Ollama)
et fournit un contexte sémantique pertinent au LLM meditron pour chaque situation.

Pipeline: KB YAML → chunks → embeddings → vector store in-memory → top-K retrieval
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np
import yaml

from app.config import settings

logger = logging.getLogger("charles.rag")


@dataclass
class KBChunk:
    """Un morceau de connaissance indexé."""
    text: str
    source: str          # e.g. "complications_perop.yaml"
    section: str         # e.g. "hemodynamiques > hypotension_post_induction"
    tags: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list, repr=False)


class RAGEngine:
    """Moteur RAG in-memory pour la KB clinique CHARLES."""

    def __init__(self, ollama_url: str | None = None, embed_model: str = "nomic-embed-text"):
        self.ollama_url = ollama_url or settings.ollama_url
        self.embed_model = embed_model
        self.chunks: list[KBChunk] = []
        self._ready = False
        self._client: httpx.AsyncClient | None = None

    @property
    def ready(self) -> bool:
        return self._ready and len(self.chunks) > 0

    async def init(self, kb_data: dict[str, Any]):
        """Initialise le RAG: chunking KB + embedding via Ollama."""
        self._client = httpx.AsyncClient(timeout=30.0)

        # Vérifier disponibilité du modèle d'embeddings
        if not await self._check_embed_model():
            logger.warning("Embedding model %s not available — RAG disabled", self.embed_model)
            return

        # Chunker la KB
        self.chunks = self._chunk_kb(kb_data)
        logger.info("KB chunked: %d chunks", len(self.chunks))

        # Générer les embeddings
        embedded = 0
        for chunk in self.chunks:
            emb = await self._embed(chunk.text)
            if emb:
                chunk.embedding = emb
                embedded += 1

        if embedded > 0:
            self._ready = True
            logger.info("RAG ready: %d/%d chunks embedded", embedded, len(self.chunks))
        else:
            logger.warning("RAG: no chunks could be embedded")

    async def close(self):
        if self._client:
            await self._client.aclose()

    async def retrieve(self, query: str, top_k: int = 5) -> list[KBChunk]:
        """Retrouve les top-K chunks les plus pertinents pour une requête."""
        if not self._ready or not self._client:
            return []

        query_emb = await self._embed(query)
        if not query_emb:
            return []

        valid_chunks = [c for c in self.chunks if c.embedding]
        if not valid_chunks:
            return []

        # Similarité cosinus vectorisée (numpy) — une seule opération matricielle
        q = np.asarray(query_emb, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        matrix = np.array([c.embedding for c in valid_chunks], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        scores = (matrix / norms) @ q   # (N,) — O(N·D) en C, non bloquant

        top_n = min(top_k, len(valid_chunks))
        top_indices = np.argpartition(scores, -top_n)[-top_n:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        return [valid_chunks[int(i)] for i in top_indices]

    def build_rag_context(self, chunks: list[KBChunk]) -> str:
        """Formate les chunks récupérés en contexte textuel pour le LLM."""
        if not chunks:
            return ""

        parts = ["## Connaissances cliniques pertinentes (KB CHARLES)"]
        for i, chunk in enumerate(chunks, 1):
            parts.append(f"\n### [{chunk.source}] {chunk.section}")
            parts.append(chunk.text)

        return "\n".join(parts)

    # ── Chunking KB ────────────────────────────────────────────

    def _chunk_kb(self, kb_data: dict[str, Any]) -> list[KBChunk]:
        """Découpe la KB YAML en chunks sémantiques."""
        chunks: list[KBChunk] = []

        for filename, data in kb_data.items():
            if not isinstance(data, dict):
                continue

            if filename == "complications_perop":
                chunks.extend(self._chunk_complications(data, filename))
            elif filename == "algorithms":
                chunks.extend(self._chunk_algorithms(data, filename))
            elif filename == "drugs_anesthesia":
                chunks.extend(self._chunk_drugs(data, filename))
            elif filename == "monitoring_params":
                chunks.extend(self._chunk_monitoring(data, filename))
            elif filename == "populations":
                chunks.extend(self._chunk_populations(data, filename))
            elif filename == "terrains":
                chunks.extend(self._chunk_terrains(data, filename))
            elif filename == "surgeries":
                chunks.extend(self._chunk_surgeries(data, filename))
            elif filename == "scores_cliniques":
                chunks.extend(self._chunk_scores(data, filename))
            else:
                # Fallback: chunk par clé de premier niveau
                chunks.extend(self._chunk_generic(data, filename))

        return chunks

    def _chunk_complications(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for system, complications in data.get("complications", {}).items():
            for comp_id, comp in complications.items():
                if not isinstance(comp, dict):
                    continue
                text_parts = [f"Complication: {comp.get('label_fr', comp_id)}"]
                if comp.get("incidence_pct"):
                    text_parts.append(f"Incidence: {comp['incidence_pct']}%")
                if comp.get("facteurs_risque"):
                    text_parts.append("Facteurs de risque: " + ", ".join(comp["facteurs_risque"]))
                pattern = comp.get("pattern_detection", {})
                for k, v in pattern.items():
                    if isinstance(v, str):
                        text_parts.append(f"Détection ({k}): {v}")
                if comp.get("conduite_anticipee"):
                    text_parts.append("Conduite à tenir: " + " | ".join(comp["conduite_anticipee"]))
                tags = [system, comp_id] + comp.get("facteurs_risque", [])[:5]
                chunks.append(KBChunk(
                    text="\n".join(text_parts),
                    source=source,
                    section=f"{system} > {comp.get('label_fr', comp_id)}",
                    tags=tags,
                ))
        return chunks

    def _chunk_algorithms(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for algo_id, algo in data.get("algorithms", {}).items():
            if not isinstance(algo, dict):
                continue
            # Un chunk par algorithme complet
            text_parts = [f"Algorithme: {algo.get('label_fr', algo_id)}"]
            if algo.get("source"):
                text_parts.append(f"Référence: {algo['source']}")
            if algo.get("trigger_charles"):
                text_parts.append(f"Déclencheur: {algo['trigger_charles']}")
            for step_id, step in algo.get("etapes", {}).items():
                if isinstance(step, dict):
                    text_parts.append(f"  {step_id}: {step.get('label', '')}")
                    for action in step.get("actions", []):
                        text_parts.append(f"    - {action}")
            chunks.append(KBChunk(
                text="\n".join(text_parts),
                source=source,
                section=algo.get("label_fr", algo_id),
                tags=[algo_id],
            ))
        return chunks

    def _chunk_drugs(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for cat_id, cat in data.get("categories", {}).items():
            if not isinstance(cat, dict):
                continue
            for drug_id, drug in cat.get("drogues", cat.get("molecules", {})).items():
                if not isinstance(drug, dict):
                    continue
                text_parts = [f"Médicament: {drug.get('label_fr', drug_id)} ({cat.get('label_fr', cat_id)})"]
                if drug.get("classe"):
                    text_parts.append(f"Classe: {drug['classe']}")
                poso = drug.get("posologie", {})
                if isinstance(poso, dict):
                    for context, doses in poso.items():
                        if isinstance(doses, dict):
                            for pop, dose in doses.items():
                                if isinstance(dose, str):
                                    text_parts.append(f"Posologie {context} {pop}: {dose}")
                        elif isinstance(doses, str):
                            text_parts.append(f"Posologie {context}: {doses}")
                for ei in drug.get("effets_secondaires", drug.get("effets_indesirables", [])):
                    text_parts.append(f"Effet indésirable: {ei}")
                for ci in drug.get("contre_indications", []):
                    text_parts.append(f"Contre-indication: {ci}")
                impact = drug.get("impact_monitoring", {})
                for param, desc in impact.items():
                    if isinstance(desc, str):
                        text_parts.append(f"Impact {param}: {desc}")
                chunks.append(KBChunk(
                    text="\n".join(text_parts),
                    source=source,
                    section=f"{cat.get('label_fr', cat_id)} > {drug.get('label_fr', drug_id)}",
                    tags=[drug_id, cat_id],
                ))
        return chunks

    def _chunk_monitoring(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for cat_id, cat in data.get("categories", {}).items():
            if not isinstance(cat, dict):
                continue
            for param_id, param in cat.get("parametres", {}).items():
                if not isinstance(param, dict):
                    continue
                text_parts = [f"Paramètre: {param.get('label_fr', param_id)}"]
                if param.get("unite"):
                    text_parts.append(f"Unité: {param['unite']}")
                if param.get("valeurs_normales"):
                    text_parts.append(f"Valeurs normales: {param['valeurs_normales']}")
                seuils = param.get("seuils_charles", {})
                if seuils:
                    text_parts.append(f"Seuils: {seuils}")
                if param.get("signification_clinique"):
                    text_parts.append(f"Signification: {param['signification_clinique']}")
                chunks.append(KBChunk(
                    text="\n".join(text_parts),
                    source=source,
                    section=f"{cat_id} > {param.get('label_fr', param_id)}",
                    tags=[param_id, cat_id],
                ))
        return chunks

    def _chunk_populations(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for pop_id, pop in data.get("populations", {}).items():
            if not isinstance(pop, dict):
                continue
            text_parts = [f"Population: {pop.get('label_fr', pop_id)}"]
            for p in pop.get("particularites_anesthesiques", []):
                text_parts.append(f"- {p}")
            alertes = pop.get("alertes_adaptees", {})
            if alertes:
                text_parts.append(f"Seuils adaptés: {alertes}")
            chunks.append(KBChunk(
                text="\n".join(text_parts),
                source=source,
                section=pop.get("label_fr", pop_id),
                tags=[pop_id],
            ))
        return chunks

    def _chunk_terrains(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for sys_id, sys_data in data.get("terrains", {}).items():
            if not isinstance(sys_data, dict):
                continue
            for pathology in sys_data.get("pathologies", []):
                if not isinstance(pathology, dict):
                    continue
                text_parts = [f"Terrain: {pathology.get('nom_fr', pathology.get('id', ''))}"]
                for imp in pathology.get("impact_anesthesique", []):
                    text_parts.append(f"- {imp}")
                for prec in pathology.get("precautions", []):
                    text_parts.append(f"Précaution: {prec}")
                chunks.append(KBChunk(
                    text="\n".join(text_parts),
                    source=source,
                    section=f"{sys_id} > {pathology.get('nom_fr', pathology.get('id', ''))}",
                    tags=[sys_id, pathology.get("id", "")],
                ))
        return chunks

    def _chunk_surgeries(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for dept_id, dept in data.get("departements", {}).items():
            if not isinstance(dept, dict):
                continue
            for proc in dept.get("procedures", []):
                if not isinstance(proc, dict):
                    continue
                text_parts = [f"Chirurgie: {proc.get('nom_fr', proc.get('id', ''))}"]
                if proc.get("duree_moyenne_min"):
                    text_parts.append(f"Durée moyenne: {proc['duree_moyenne_min']} min")
                if proc.get("risque_hemorragique"):
                    text_parts.append(f"Risque hémorragique: {proc['risque_hemorragique']}")
                for r in proc.get("risques_specifiques", []):
                    text_parts.append(f"Risque: {r}")
                for tech in proc.get("techniques_anesthesie", []):
                    text_parts.append(f"Technique: {tech}")
                chunks.append(KBChunk(
                    text="\n".join(text_parts),
                    source=source,
                    section=f"{dept_id} > {proc.get('nom_fr', proc.get('id', ''))}",
                    tags=[dept_id, proc.get("id", "")],
                ))
        return chunks

    def _chunk_scores(self, data: dict, source: str) -> list[KBChunk]:
        chunks = []
        for score_id, score in data.get("scores", {}).items():
            if not isinstance(score, dict):
                continue
            text_parts = [f"Score: {score.get('label_fr', score_id)}"]
            if score.get("description"):
                text_parts.append(score["description"])
            if score.get("composantes"):
                for comp in score["composantes"]:
                    if isinstance(comp, str):
                        text_parts.append(f"- {comp}")
                    elif isinstance(comp, dict):
                        text_parts.append(f"- {comp}")
            if score.get("interpretation"):
                text_parts.append(f"Interprétation: {score['interpretation']}")
            chunks.append(KBChunk(
                text="\n".join(text_parts),
                source=source,
                section=score.get("label_fr", score_id),
                tags=[score_id],
            ))
        return chunks

    def _chunk_generic(self, data: dict, source: str) -> list[KBChunk]:
        """Fallback: un chunk par clé de premier niveau."""
        chunks = []
        for key, value in data.items():
            if key.startswith("#") or key.startswith("_"):
                continue
            text = yaml.dump({key: value}, allow_unicode=True, default_flow_style=False)
            # Limiter la taille des chunks
            if len(text) > 2000:
                text = text[:2000] + "\n..."
            chunks.append(KBChunk(
                text=text,
                source=source,
                section=key,
                tags=[key],
            ))
        return chunks

    # ── Embeddings ─────────────────────────────────────────────

    async def _check_embed_model(self) -> bool:
        """Vérifie que le modèle d'embeddings est disponible dans Ollama."""
        try:
            r = await self._client.get(f"{self.ollama_url}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                available = any(self.embed_model.split(":")[0] in m for m in models)
                if available:
                    logger.info("Embedding model %s available", self.embed_model)
                return available
        except Exception as e:
            logger.warning("Cannot check embedding model: %s", e)
        return False

    async def _embed(self, text: str) -> list[float] | None:
        """Génère un embedding via Ollama."""
        try:
            r = await self._client.post(
                f"{self.ollama_url}/api/embed",
                json={"model": self.embed_model, "input": text},
            )
            if r.status_code == 200:
                data = r.json()
                embeddings = data.get("embeddings", [])
                if embeddings:
                    return embeddings[0]
        except Exception as e:
            logger.debug("Embedding failed: %s", e)
        return None
