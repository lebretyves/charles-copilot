"""
CHARLES — LLM Engine.

Intègre un LLM (Ollama local ou API OpenAI/Anthropic) pour analyser
la situation clinique et fournir des recommandations IADE.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from app.config import settings
from app.models import Alert, LLMAnalysis, VitalsFrame
from app.rag_engine import RAGEngine

logger = logging.getLogger("charles.llm")

# Prompt système pour le LLM — rôle d'expert anesthésie
SYSTEM_PROMPT = """Tu es CHARLES, un copilote IA d'aide à la vigilance anesthésique peropératoire.
Tu assistes un(e) IADE (Infirmier Anesthésiste Diplômé d'État) pendant une intervention chirurgicale.

Ton rôle :
1. Analyser la situation clinique à partir des paramètres vitaux, alertes et contexte
2. Proposer des diagnostics différentiels classés par probabilité
3. Recommander des conduites à tenir immédiates (actions IADE autonomes)
4. Identifier ce qui nécessite d'appeler le MAR (Médecin Anesthésiste-Réanimateur)

Règles :
- Sois concis et priorise l'urgence vitale
- Utilise la terminologie médicale IADE (pas de vulgarisation)
- Base tes recommandations sur les référentiels SFAR, ASA, ESA
- Indique ton niveau de confiance
- Ne remplace JAMAIS le jugement clinique de l'IADE — tu es un outil d'aide

Format de réponse STRICTEMENT en JSON :
{
  "situation": "résumé clinique en 1-2 phrases",
  "risks": ["risque 1", "risque 2"],
  "recommendations": ["action 1", "action 2"],
  "call_mar": true/false,
  "call_mar_reason": "raison si true",
  "confidence": 0.0-1.0
}"""


class LLMEngine:
    """Moteur LLM pour l'analyse clinique."""

    def __init__(self, kb=None):
        self.kb = kb
        self.rag: RAGEngine | None = None
        self._client: httpx.AsyncClient | None = None
        self._available = False
        # Support Ollama (local) ou API compatible OpenAI
        self.ollama_url = getattr(settings, "ollama_url", "http://localhost:11434")
        self.ollama_model = getattr(settings, "ollama_model", "llama3.1:8b")
        self.openai_api_key = getattr(settings, "openai_api_key", "")
        self.openai_model = getattr(settings, "openai_model", "gpt-4o-mini")
        self.provider = getattr(settings, "llm_provider", "ollama")  # ollama | openai

    async def init(self):
        """Initialise le client HTTP et vérifie la disponibilité du LLM."""
        self._client = httpx.AsyncClient(timeout=60.0)

        if self.provider == "ollama":
            try:
                r = await self._client.get(f"{self.ollama_url}/api/tags")
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    self._available = any(self.ollama_model.split(":")[0] in m for m in models)
                    if self._available:
                        logger.info("LLM ready: Ollama %s", self.ollama_model)
                    else:
                        logger.warning("Ollama running but model %s not found. Available: %s", self.ollama_model, models)
            except Exception:
                logger.info("Ollama not available — LLM disabled (run 'ollama pull %s')", self.ollama_model)
        elif self.provider == "openai" and self.openai_api_key:
            self._available = True
            logger.info("LLM ready: OpenAI %s", self.openai_model)

    async def init_rag(self, kb_data: dict):
        """Initialise le moteur RAG avec les données KB."""
        self.rag = RAGEngine(ollama_url=self.ollama_url)
        await self.rag.init(kb_data)
        if self.rag.ready:
            logger.info("RAG engine ready (%d chunks)", len(self.rag.chunks))
        else:
            logger.warning("RAG engine not available — falling back to keyword KB context")

    async def close(self):
        if self.rag:
            await self.rag.close()
        if self._client:
            await self._client.aclose()

    @property
    def available(self) -> bool:
        return self._available

    async def analyze(
        self,
        vitals: VitalsFrame,
        alerts: list[Alert],
        room_id: str,
        case_context: dict[str, Any] | None = None,
    ) -> LLMAnalysis | None:
        """Analyse la situation clinique et retourne des recommandations."""
        if not self._available or not self._client:
            return None

        # Construire le prompt utilisateur
        user_prompt = self._build_prompt(vitals, alerts, case_context)

        # Enrichir avec RAG sémantique si disponible
        if self.rag and self.rag.ready:
            rag_query = self._build_rag_query(vitals, alerts)
            rag_chunks = await self.rag.retrieve(rag_query, top_k=5)
            if rag_chunks:
                rag_context = self.rag.build_rag_context(rag_chunks)
                user_prompt = user_prompt.replace(
                    "\nAnalyse cette situation et réponds en JSON.",
                    f"\n{rag_context}\n\nAnalyse cette situation et réponds en JSON.",
                )

        start_ms = time.monotonic_ns() // 1_000_000

        try:
            if self.provider == "ollama":
                result = await self._call_ollama(user_prompt)
            else:
                result = await self._call_openai(user_prompt)
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            return None

        latency_ms = (time.monotonic_ns() // 1_000_000) - start_ms

        if not result:
            return None

        return LLMAnalysis(
            situation=result.get("situation", "Analyse indisponible"),
            risks=result.get("risks", []),
            recommendations=result.get("recommendations", []),
            confidence=min(1.0, max(0.0, result.get("confidence", 0.5))),
            call_mar=bool(result.get("call_mar", False)),
            call_mar_reason=result.get("call_mar_reason"),
            model=self.ollama_model if self.provider == "ollama" else self.openai_model,
            latency_ms=latency_ms,
            prompt_tokens=int(result.get("_prompt_tokens", 0) or 0),
            completion_tokens=int(result.get("_completion_tokens", 0) or 0),
        )

    def _build_prompt(
        self,
        vitals: VitalsFrame,
        alerts: list[Alert],
        case_context: dict[str, Any] | None = None,
    ) -> str:
        """Construit le prompt utilisateur avec vitaux + alertes + contexte KB."""
        parts = []

        # Vitaux actuels
        parts.append("## Paramètres vitaux actuels")
        parts.append(f"- FC: {vitals.hr} bpm")
        parts.append(f"- SpO2: {vitals.spo2}%")
        parts.append(f"- PA: {vitals.pas}/{vitals.pad} (PAM {vitals.pam}) mmHg")
        parts.append(f"- EtCO2: {vitals.etco2} mmHg")
        parts.append(f"- FR: {vitals.fr}/min")
        parts.append(f"- T°: {vitals.temp}°C")

        # Alertes actives
        if alerts:
            parts.append("\n## Alertes actives")
            for a in alerts:
                parts.append(f"- [{a.level.upper()}] {a.title}: {a.detail}")

        # Contexte cas (chirurgie, patient, médicaments)
        if case_context:
            if case_context.get("surgery_type"):
                parts.append(f"\n## Contexte chirurgical")
                parts.append(f"- Chirurgie: {case_context['surgery_type']}")
                if case_context.get("anesthesia_type"):
                    parts.append(f"- Anesthésie: {case_context['anesthesia_type']}")
            if case_context.get("patient_age"):
                parts.append(f"- Patient: {case_context['patient_age']} ans, ASA {case_context.get('asa_score', '?')}")

        # Contexte KB enrichi — RAG sémantique si disponible, sinon fallback keyword

        if self.kb and self.kb.loaded:
            kb_context = self.kb.get_context_for_llm(
                surgery_type=case_context.get("surgery_type") if case_context else None,
                population=case_context.get("population") if case_context else None,
                terrain=case_context.get("terrain") if case_context else None,
                active_drugs=case_context.get("active_drugs") if case_context else None,
            )
            if kb_context and kb_context != "Pas de contexte KB spécifique disponible.":
                parts.append(f"\n## Connaissances cliniques\n{kb_context}")

        parts.append("\nAnalyse cette situation et réponds en JSON.")
        return "\n".join(parts)

    async def _call_ollama(self, user_prompt: str) -> dict | None:
        r = await self._client.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.ollama_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.3, "num_predict": 512},
            },
        )
        if r.status_code != 200:
            logger.error("Ollama error %d: %s", r.status_code, r.text[:200])
            return None

        raw = r.json()
        content = raw.get("message", {}).get("content", "")
        parsed = self._parse_json_response(content)
        if not parsed:
            return None
        parsed["_prompt_tokens"] = int(raw.get("prompt_eval_count") or 0)
        parsed["_completion_tokens"] = int(raw.get("eval_count") or 0)
        return parsed

    async def _call_openai(self, user_prompt: str) -> dict | None:
        r = await self._client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.openai_api_key}"},
            json={
                "model": self.openai_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 512,
                "response_format": {"type": "json_object"},
            },
        )
        if r.status_code != 200:
            logger.error("OpenAI error %d: %s", r.status_code, r.text[:200])
            return None

        raw = r.json()
        content = raw["choices"][0]["message"]["content"]
        parsed = self._parse_json_response(content)
        if not parsed:
            return None
        usage = raw.get("usage", {})
        parsed["_prompt_tokens"] = int(usage.get("prompt_tokens") or 0)
        parsed["_completion_tokens"] = int(usage.get("completion_tokens") or 0)
        return parsed

    def _build_rag_query(self, vitals: VitalsFrame, alerts: list[Alert]) -> str:
        """Construit une requête concise pour le RAG à partir de la situation."""
        parts = []
        # Les alertes sont le signal le plus important
        for a in alerts:
            parts.append(f"{a.title}: {a.detail}")
        # Ajouter les vitaux anormaux
        if vitals.spo2 and vitals.spo2 < 95:
            parts.append(f"SpO2 basse {vitals.spo2}%")
        if vitals.pam and vitals.pam < 65:
            parts.append(f"Hypotension PAM {vitals.pam}")
        if vitals.hr and (vitals.hr < 50 or vitals.hr > 120):
            parts.append(f"FC anormale {vitals.hr}")
        if vitals.etco2 and (vitals.etco2 < 30 or vitals.etco2 > 45):
            parts.append(f"EtCO2 anormal {vitals.etco2}")
        return " | ".join(parts) if parts else "surveillance anesthésie standard"

    def _parse_json_response(self, content: str) -> dict | None:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Tenter d'extraire le JSON d'un bloc markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    pass
            logger.warning("LLM returned non-JSON: %s", content[:200])
            return None
