"""Event trace agent built as a LangGraph-style evidence workflow."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Awaitable, Callable, TypedDict
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from .llm import LLMClient
from .schema import Message


SearchProvider = Callable[[str, int], Awaitable[list["Source"]]]
FetchProvider = Callable[["Source"], Awaitable["Page"]]
EvidenceExtractor = Callable[["Page"], Awaitable[list["Evidence"]]]


@dataclass
class Source:
    """Candidate source returned by search."""

    url: str
    title: str = ""
    snippet: str = ""
    source_type: str = "web"
    relevance: float = 0.0


@dataclass
class Page:
    """Fetched page with normalized text."""

    url: str
    title: str = ""
    text: str = ""
    published_at: str | None = None
    author: str | None = None
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")
    error: str | None = None


@dataclass
class Evidence:
    """Structured evidence extracted from a page."""

    event_time: str
    actor: str
    action: str
    claim: str
    source_url: str
    source_title: str = ""
    quote: str = ""
    published_at: str | None = None
    location: str | None = None
    confidence: float = 0.5
    validation_status: str = "unverified"


@dataclass
class EventCluster:
    """Evidence cluster representing one timeline event."""

    event_time: str
    summary: str
    actor: str = ""
    evidences: list[Evidence] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    confidence: float = 0.0
    validation_status: str = "unverified"


@dataclass
class TimelineItem:
    """Timeline item derived from an event cluster."""

    event_time: str
    summary: str
    citations: list[str]
    confidence: float
    validation_status: str


@dataclass
class ValidationNote:
    """Validation note for one event or the whole run."""

    target: str
    status: str
    message: str


@dataclass
class CitationJudgment:
    """Whether a quote supports a claim."""

    status: str
    reason: str = ""


@dataclass
class TraceTaskPlan:
    """Responsible task plan for one event trace run."""

    topic: str
    objective: str
    research_depth: str = "quick"
    time_range: str | None = None
    focus: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    required_questions: list[str] = field(default_factory=list)
    source_strategy: list[str] = field(default_factory=list)
    evidence_requirements: list[str] = field(default_factory=list)
    validation_rules: list[str] = field(default_factory=list)
    safety_constraints: list[str] = field(default_factory=list)
    memory_hints: list[str] = field(default_factory=list)


class TraceTaskPlanPayload(BaseModel):
    """Validated LLM payload for task planning."""

    objective: str = Field(default="", max_length=500)
    search_queries: list[str] = Field(default_factory=list, max_length=12)
    required_questions: list[str] = Field(default_factory=list, max_length=12)
    source_strategy: list[str] = Field(default_factory=list, max_length=12)
    evidence_requirements: list[str] = Field(default_factory=list, max_length=12)
    validation_rules: list[str] = Field(default_factory=list, max_length=12)
    safety_constraints: list[str] = Field(default_factory=list, max_length=12)

    @field_validator(
        "search_queries",
        "required_questions",
        "source_strategy",
        "evidence_requirements",
        "validation_rules",
        "safety_constraints",
    )
    @classmethod
    def clean_list(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = str(item).strip()
            if text:
                cleaned.append(text[:300])
        return list(dict.fromkeys(cleaned))


class EvidencePayload(BaseModel):
    """Validated LLM payload for evidence extraction."""

    event_time: str = "unknown"
    actor: str = ""
    action: str = "reported"
    claim: str = Field(min_length=1, max_length=700)
    location: str | None = None
    quote: str = Field(default="", max_length=700)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)

    @field_validator("event_time", "actor", "action", "claim", "quote")
    @classmethod
    def clean_string(cls, value: str) -> str:
        return str(value).strip()


class CitationJudgmentPayload(BaseModel):
    """Validated LLM payload for citation judging."""

    status: str
    reason: str = ""

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        status = str(value).strip().lower()
        if status not in {"supported", "unsupported", "unclear"}:
            raise ValueError("status must be supported, unsupported, or unclear")
        return status

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return str(value).strip()[:300]


class EventTraceState(TypedDict, total=False):
    """Graph state for event tracing."""

    topic: str
    research_depth: str
    time_range: str | None
    focus: list[str]
    task_plan: TraceTaskPlan
    queries: list[str]
    candidate_sources: list[Source]
    pages: list[Page]
    evidences: list[Evidence]
    event_clusters: list[EventCluster]
    timeline: list[TimelineItem]
    validation_notes: list[ValidationNote]
    report: str
    search_round: int
    weak_evidence_count: int
    run_id: str


class _TextExtractor(HTMLParser):
    """Small HTML text extractor without extra dependencies."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.title = ""
        self._in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or self._skip_depth:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        self.parts.append(text)

    def text(self) -> str:
        return _normalize_text(" ".join(self.parts))


def _normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def _token_set(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[\w\u4e00-\u9fff]{2,}", text)}


def _overlap_score(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _first_date(text: str) -> str:
    patterns = [
        r"\b(20\d{2}[-/\.](?:0?[1-9]|1[0-2])[-/\.](?:0?[1-9]|[12]\d|3[01]))\b",
        r"\b(20\d{2}-(?:0?[1-9]|1[0-2]))\b",
        r"\b(20\d{2})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).replace("/", "-").replace(".", "-")
    return "unknown"


def _sentence_split(text: str) -> list[str]:
    candidates = re.split(r"(?<=[。.!?])\s+", text)
    return [item.strip() for item in candidates if len(item.strip()) >= 20]


def _json_array_from_text(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    return data if isinstance(data, list) else []


def _json_object_from_text(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


class EventTraceMemory:
    """JSONL evidence memory scoped to one workspace."""

    def __init__(self, memory_file: str | Path):
        self.memory_file = Path(memory_file).expanduser()
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)

    def recall_evidences(self, topic: str, limit: int = 5) -> list[Evidence]:
        if not self.memory_file.exists():
            return []
        scored: list[tuple[float, Evidence]] = []
        for line in self.memory_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if item.get("type") != "evidence":
                    continue
                evidence = Evidence(**item["payload"])
            except Exception:
                continue
            score = max(
                _overlap_score(topic, evidence.claim),
                _overlap_score(topic, evidence.source_title),
            )
            if score > 0:
                scored.append((score, evidence))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [evidence for _, evidence in scored[:limit]]

    def append_evidences(self, topic: str, evidences: list[Evidence]) -> None:
        if not evidences:
            return
        with self.memory_file.open("a", encoding="utf-8") as f:
            for evidence in evidences:
                f.write(
                    json.dumps(
                        {
                            "type": "evidence",
                            "topic": topic,
                            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                            "payload": asdict(evidence),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )


class EventTraceRunRecorder:
    """Persist event trace run state and audit records."""

    def __init__(self, run_dir: str | Path, run_id: str | None = None):
        self.run_dir = Path(run_dir).expanduser()
        self.run_id = run_id or self.run_dir.name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.audit_file = self.run_dir / "audit.jsonl"
        self.state_file = self.run_dir / "state.json"
        self.report_file = self.run_dir / "report.md"

    def record_node(self, node: str, state: EventTraceState, started_at: float, error: str | None = None) -> None:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        record = {
            "run_id": self.run_id,
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "node": node,
            "elapsed_ms": elapsed_ms,
            "error": error,
            "counts": self._counts(state),
        }
        with self.audit_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.write_state(state)

    def write_state(self, state: EventTraceState) -> None:
        self.state_file.write_text(json.dumps(state_to_jsonable(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def write_report(self, report: str) -> None:
        self.report_file.write_text(report, encoding="utf-8")

    def _counts(self, state: EventTraceState) -> dict[str, int]:
        return {
            "queries": len(state.get("queries", [])),
            "sources": len(state.get("candidate_sources", [])),
            "pages": len(state.get("pages", [])),
            "evidences": len(state.get("evidences", [])),
            "event_clusters": len(state.get("event_clusters", [])),
            "timeline": len(state.get("timeline", [])),
            "validation_notes": len(state.get("validation_notes", [])),
        }


class ResponsibleTaskPlanner:
    """Create an explicit, auditable plan before evidence collection."""

    def __init__(
        self,
        memory: EventTraceMemory | None = None,
        llm_client: LLMClient | None = None,
        research_depth: str = "quick",
        time_range: str | None = None,
        focus: list[str] | None = None,
    ):
        self.memory = memory
        self.llm_client = llm_client
        self.research_depth = research_depth if research_depth in {"quick", "deep"} else "quick"
        self.time_range = time_range.strip() if time_range else None
        self.focus = [item.strip() for item in focus or [] if item.strip()]

    async def plan(self, topic: str) -> TraceTaskPlan:
        rule_plan = self._rule_plan(topic)
        if not self.llm_client:
            return rule_plan

        try:
            llm_plan = await self._llm_plan(topic, rule_plan)
        except Exception:
            return rule_plan
        if llm_plan is None:
            return rule_plan
        return self._merge_with_rule_plan(rule_plan, llm_plan)

    def _rule_plan(self, topic: str) -> TraceTaskPlan:
        recalled = self.memory.recall_evidences(topic, limit=5) if self.memory else []
        memory_hints = self._memory_hints(recalled)
        actor_hints = [evidence.actor for evidence in recalled if evidence.actor]

        search_queries = [
            topic,
            f"{topic} timeline",
            f"{topic} official response",
            f"{topic} incident report",
            f"{topic} controversy source",
        ]
        if self.time_range:
            search_queries.extend(
                [
                    f"{topic} {self.time_range}",
                    f"{topic} timeline {self.time_range}",
                ]
            )
        for focus_item in self.focus[:5]:
            search_queries.append(f"{topic} {focus_item}")
            if self.time_range:
                search_queries.append(f"{topic} {focus_item} {self.time_range}")
        if self.research_depth == "deep":
            search_queries.extend(
                [
                    f"{topic} primary sources",
                    f"{topic} international response",
                    f"{topic} disputed claims",
                    f"{topic} analysis report",
                ]
            )
        for actor in actor_hints[:3]:
            search_queries.append(f"{topic} {actor}")

        return TraceTaskPlan(
            topic=topic,
            objective=(
                "Build a cited event trace that separates confirmed facts, "
                "single-source claims, conflicts, and information gaps."
            ),
            research_depth=self.research_depth,
            time_range=self.time_range,
            focus=self.focus,
            search_queries=list(dict.fromkeys(search_queries)),
            required_questions=[
                "What happened first, and when did it happen?",
                "Who are the main actors, organizations, or affected parties?",
                "What official responses, corrections, or follow-up actions exist?",
                "Which claims are supported by multiple independent sources?",
                "Which claims remain disputed, weakly sourced, or missing evidence?",
            ],
            source_strategy=[
                "Prefer official statements, primary documents, reputable media, and regulator or court records.",
                "Use at least two independent source URLs before marking an event as supported.",
                "Keep low-confidence social or forum posts as provisional unless corroborated.",
            ],
            evidence_requirements=[
                "Every event claim must preserve source_url and an original quote.",
                "Track event_time separately from published_at.",
                "Do not promote a model summary to evidence unless it is grounded in a quote.",
            ],
            validation_rules=[
                "supported: at least two source URLs support the event cluster.",
                "single_source: only one source URL supports the event cluster.",
                "conflicted: sources disagree on time, actor, action, or outcome.",
            ],
            safety_constraints=[
                "Do not fetch private, localhost, or internal network URLs.",
                "Do not execute shell commands as part of event tracing.",
                "Do not store sensitive private material in reusable memory.",
            ],
            memory_hints=memory_hints,
        )

    async def _llm_plan(self, topic: str, rule_plan: TraceTaskPlan) -> TraceTaskPlan | None:
        prompt = f"""
Create a responsible event tracing task plan.
Return only a JSON object with these keys:
objective, search_queries, required_questions, source_strategy,
evidence_requirements, validation_rules, safety_constraints.

Constraints:
- Keep the plan focused on the topic.
- Search queries should be concrete and diverse.
- Evidence requirements must preserve source_url, quote, event_time, and published_at.
- Validation rules must distinguish supported, single_source, and conflicted.
- Safety constraints must not request shell execution, private sources, or internal network access.
- Do not include prose outside JSON.

Topic: {topic}
Research depth: {self.research_depth}
Time range: {self.time_range or "not specified"}
Focus: {", ".join(self.focus) if self.focus else "not specified"}
Rule baseline:
{json.dumps(asdict(rule_plan), ensure_ascii=False, indent=2)}
""".strip()
        response = await self.llm_client.generate([Message(role="user", content=prompt)])
        data = _json_object_from_text(response.content)
        if not data:
            return None
        try:
            payload = TraceTaskPlanPayload.model_validate(data)
        except ValidationError:
            return None

        return TraceTaskPlan(
            topic=topic,
            objective=payload.objective.strip() or rule_plan.objective,
            research_depth=rule_plan.research_depth,
            time_range=rule_plan.time_range,
            focus=rule_plan.focus,
            search_queries=payload.search_queries,
            required_questions=payload.required_questions,
            source_strategy=payload.source_strategy,
            evidence_requirements=payload.evidence_requirements,
            validation_rules=payload.validation_rules,
            safety_constraints=payload.safety_constraints,
            memory_hints=rule_plan.memory_hints,
        )

    def _merge_with_rule_plan(self, rule_plan: TraceTaskPlan, llm_plan: TraceTaskPlan) -> TraceTaskPlan:
        return TraceTaskPlan(
            topic=rule_plan.topic,
            objective=llm_plan.objective or rule_plan.objective,
            research_depth=rule_plan.research_depth,
            time_range=rule_plan.time_range,
            focus=rule_plan.focus,
            search_queries=self._dedupe(rule_plan.search_queries + llm_plan.search_queries)[:12],
            required_questions=self._dedupe(rule_plan.required_questions + llm_plan.required_questions)[:12],
            source_strategy=self._dedupe(rule_plan.source_strategy + llm_plan.source_strategy)[:12],
            evidence_requirements=self._dedupe(rule_plan.evidence_requirements + llm_plan.evidence_requirements)[:12],
            validation_rules=self._dedupe(rule_plan.validation_rules + llm_plan.validation_rules)[:12],
            safety_constraints=self._dedupe(rule_plan.safety_constraints + llm_plan.safety_constraints)[:12],
            memory_hints=rule_plan.memory_hints,
        )

    def _dedupe(self, items: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in items if item))

    def _memory_hints(self, evidences: list[Evidence]) -> list[str]:
        hints = []
        for evidence in evidences:
            label = evidence.actor or evidence.source_title or evidence.source_url
            hints.append(f"Prior evidence: {label} | {evidence.event_time} | {evidence.claim[:160]}")
        return hints


class TavilySearchProvider:
    """Tavily-backed search provider used by the event trace workflow."""

    def __init__(self, api_key: str = "", endpoint: str = "https://api.tavily.com/search", timeout: float = 20.0):
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout

    async def __call__(self, query: str, max_results: int) -> list[Source]:
        if not self.api_key:
            return []
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max(1, min(max_results, 10)),
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return []

        sources = []
        for item in data.get("results", []):
            sources.append(
                Source(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("content", "") or item.get("snippet", ""),
                    source_type="web",
                    relevance=float(item.get("score", 0) or 0),
                )
            )
        return [source for source in sources if source.url]


class NetworkPolicy:
    """Network guard for page fetching."""

    BLOCKED_HOSTS = {"localhost", "0.0.0.0"}
    PROXY_FAKE_IP_NETWORKS = (ipaddress.ip_network("198.18.0.0/15"),)

    def __init__(
        self,
        allow_private_network: bool = False,
        max_response_bytes: int = 2_000_000,
        allow_proxy_fake_ip: bool = True,
    ):
        self.allow_private_network = allow_private_network
        self.max_response_bytes = max_response_bytes
        self.allow_proxy_fake_ip = allow_proxy_fake_ip

    async def validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported network scheme: {parsed.scheme}")
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("URL hostname is required")
        if hostname.lower() in self.BLOCKED_HOSTS:
            raise ValueError(f"Blocked hostname: {hostname}")
        if self.allow_private_network:
            return

        hostname_is_ip = self._hostname_is_ip_literal(hostname)
        addr_infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
        for addr_info in addr_infos:
            address = addr_info[4][0]
            ip = ipaddress.ip_address(address)
            if self._is_allowed_proxy_fake_ip(ip, hostname_is_ip):
                continue
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
                raise ValueError(f"Blocked private or non-public address: {ip}")

    def _hostname_is_ip_literal(self, hostname: str) -> bool:
        try:
            ipaddress.ip_address(hostname)
            return True
        except ValueError:
            return False

    def _is_allowed_proxy_fake_ip(self, ip: ipaddress._BaseAddress, hostname_is_ip: bool) -> bool:
        if not self.allow_proxy_fake_ip or hostname_is_ip:
            return False
        return any(ip in network for network in self.PROXY_FAKE_IP_NETWORKS)


class DefaultPageFetcher:
    """Fetch web, file://, or local-path sources."""

    def __init__(
        self,
        *,
        cache_dir: str | Path | None = None,
        network_policy: NetworkPolicy | None = None,
        timeout: float = 20.0,
    ):
        self.cache_dir = Path(cache_dir).expanduser() if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.network_policy = network_policy or NetworkPolicy()
        self.timeout = timeout

    async def __call__(self, source: Source) -> Page:
        parsed = urlparse(source.url)
        try:
            if parsed.scheme == "file":
                path = Path(parsed.path)
                content = path.read_text(encoding="utf-8")
            elif parsed.scheme in {"http", "https"}:
                cached_page = self._read_cache(source.url)
                if cached_page:
                    return cached_page
                await self.network_policy.validate_url(source.url)
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(source.url, headers={"User-Agent": "mini-agent-event-trace/0.1"})
                    response.raise_for_status()
                    if len(response.content) > self.network_policy.max_response_bytes:
                        raise ValueError(f"Response too large: {len(response.content)} bytes")
                    content = response.text
            else:
                path = Path(source.url)
                content = path.read_text(encoding="utf-8")

            extractor = _TextExtractor()
            if "<html" in content[:500].lower() or "</" in content[:2000]:
                extractor.feed(content)
                title = source.title or extractor.title
                text = extractor.text()
            else:
                title = source.title
                text = _normalize_text(content)

            page = Page(
                url=source.url,
                title=title,
                text=text,
                published_at=_first_date(f"{source.snippet} {text}"),
            )
            if parsed.scheme in {"http", "https"}:
                self._write_cache(page)
            return page
        except Exception as exc:
            return Page(url=source.url, title=source.title, text="", error=str(exc))

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, url: str) -> Page | None:
        cache_path = self._cache_path(url)
        if not cache_path or not cache_path.exists():
            return None
        try:
            return Page(**json.loads(cache_path.read_text(encoding="utf-8")))
        except Exception:
            return None

    def _write_cache(self, page: Page) -> None:
        cache_path = self._cache_path(page.url)
        if not cache_path:
            return
        cache_path.write_text(json.dumps(asdict(page), ensure_ascii=False, indent=2), encoding="utf-8")


class HeuristicEvidenceExtractor:
    """Deterministic fallback extractor for offline runs and tests."""

    async def __call__(self, page: Page) -> list[Evidence]:
        if page.error or not page.text:
            return []
        sentences = _sentence_split(page.text)
        if not sentences:
            sentences = [page.text[:500]]

        evidences = []
        for sentence in sentences[:4]:
            event_time = _first_date(sentence)
            if event_time == "unknown":
                event_time = page.published_at or "unknown"
            actor = sentence.split(" ", 1)[0][:80] if sentence else ""
            evidences.append(
                Evidence(
                    event_time=event_time,
                    actor=actor,
                    action="reported",
                    claim=sentence[:500],
                    source_url=page.url,
                    source_title=page.title,
                    quote=sentence[:500],
                    published_at=page.published_at,
                    confidence=0.45,
                )
            )
        return evidences


class LLMEvidenceExtractor:
    """LLM-backed extractor that returns structured evidence JSON."""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.fallback = HeuristicEvidenceExtractor()

    async def __call__(self, page: Page) -> list[Evidence]:
        if page.error or not page.text:
            return []

        prompt = f"""
Extract event evidence from the page below.
Return only a JSON array. Each item must contain:
event_time, actor, action, claim, location, quote, confidence.
Use "unknown" when event_time is not stated. Quote must be copied from the page text.

Title: {page.title}
URL: {page.url}
Published at: {page.published_at or "unknown"}
Text:
{page.text[:8000]}
""".strip()
        try:
            response = await self.llm_client.generate([Message(role="user", content=prompt)])
            items = _json_array_from_text(response.content)
        except Exception:
            return await self.fallback(page)

        evidences = []
        for item in items[:8]:
            if not isinstance(item, dict):
                continue
            try:
                payload = EvidencePayload.model_validate(item)
            except ValidationError:
                continue
            evidences.append(
                Evidence(
                    event_time=payload.event_time or page.published_at or "unknown",
                    actor=payload.actor,
                    action=payload.action or "reported",
                    claim=payload.claim,
                    source_url=page.url,
                    source_title=page.title,
                    quote=payload.quote or payload.claim,
                    published_at=page.published_at,
                    location=payload.location,
                    confidence=payload.confidence,
                )
            )
        if not evidences:
            return await self.fallback(page)
        return evidences


class CitationJudge:
    """Judge whether evidence quotes support claims, with LLM optional."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client

    async def judge(self, evidence: Evidence) -> CitationJudgment:
        rule_judgment = self._rule_judge(evidence)
        if not self.llm_client:
            return rule_judgment
        try:
            llm_judgment = await self._llm_judge(evidence)
        except Exception:
            return rule_judgment
        return llm_judgment or rule_judgment

    def _rule_judge(self, evidence: Evidence) -> CitationJudgment:
        claim = evidence.claim.strip()
        quote = evidence.quote.strip()
        if not claim or not quote:
            return CitationJudgment(status="unsupported", reason="Missing claim or quote.")
        if claim in quote or quote in claim:
            return CitationJudgment(status="supported", reason="Claim and quote overlap directly.")
        score = _overlap_score(claim, quote)
        if score >= 0.35:
            return CitationJudgment(status="supported", reason=f"Claim and quote token overlap is {score:.2f}.")
        if score >= 0.15:
            return CitationJudgment(status="unclear", reason=f"Claim and quote token overlap is {score:.2f}.")
        return CitationJudgment(status="unsupported", reason=f"Claim and quote token overlap is {score:.2f}.")

    async def _llm_judge(self, evidence: Evidence) -> CitationJudgment | None:
        prompt = f"""
Only based on the quote, decide whether it supports the claim.
Return only JSON with keys: status, reason.
status must be one of: supported, unsupported, unclear.
Do not use outside knowledge.

Claim: {evidence.claim}
        Quote: {evidence.quote}
""".strip()
        response = await self.llm_client.generate([Message(role="user", content=prompt)])
        data = _json_object_from_text(response.content)
        if not data:
            return None
        try:
            payload = CitationJudgmentPayload.model_validate(data)
        except ValidationError:
            return None
        return CitationJudgment(status=payload.status, reason=payload.reason)


class ConflictDetector:
    """Detect simple source conflicts within an event cluster."""

    OPPOSING_TERMS = [
        ({"confirmed", "admitted", "reported", "said", "确认", "承认"}, {"denied", "rejected", "disputed", "否认", "驳斥"}),
        ({"increase", "increased", "rise", "rose", "上涨", "增加"}, {"decrease", "decreased", "fall", "fell", "下跌", "减少"}),
    ]

    def detect(self, evidences: list[Evidence]) -> ValidationNote | None:
        if len({evidence.source_url for evidence in evidences}) < 2:
            return None

        texts = [f"{evidence.action} {evidence.claim} {evidence.quote}".lower() for evidence in evidences]
        for left_terms, right_terms in self.OPPOSING_TERMS:
            has_left = any(any(term in text for term in left_terms) for text in texts)
            has_right = any(any(term in text for term in right_terms) for text in texts)
            if has_left and has_right:
                return ValidationNote(
                    target=evidences[0].claim[:120],
                    status="conflicted",
                    message="Supported sources contain opposing claim signals.",
                )
        return None


class EventTraceAgent:
    """Event trace workflow with optional LangGraph runtime."""

    def __init__(
        self,
        *,
        topic: str,
        search_provider: SearchProvider | None = None,
        fetch_provider: FetchProvider | None = None,
        evidence_extractor: EvidenceExtractor | None = None,
        task_planner: ResponsibleTaskPlanner | None = None,
        citation_judge: CitationJudge | None = None,
        conflict_detector: ConflictDetector | None = None,
        run_recorder: EventTraceRunRecorder | None = None,
        memory: EventTraceMemory | None = None,
        initial_sources: list[Source] | None = None,
        max_sources: int = 8,
        max_search_rounds: int = 2,
        use_langgraph: bool = True,
        research_depth: str = "quick",
        time_range: str | None = None,
        focus: list[str] | None = None,
    ):
        self.topic = topic
        self.research_depth = research_depth if research_depth in {"quick", "deep"} else "quick"
        self.time_range = time_range
        self.focus = [item.strip() for item in focus or [] if item.strip()]
        self.search_provider = search_provider or TavilySearchProvider()
        self.fetch_provider = fetch_provider or DefaultPageFetcher()
        self.evidence_extractor = evidence_extractor or HeuristicEvidenceExtractor()
        self.memory = memory
        self.task_planner = task_planner or ResponsibleTaskPlanner(
            memory=memory,
            research_depth=self.research_depth,
            time_range=self.time_range,
            focus=self.focus,
        )
        self.citation_judge = citation_judge or CitationJudge()
        self.conflict_detector = conflict_detector or ConflictDetector()
        self.run_recorder = run_recorder
        self.initial_sources = initial_sources or []
        self.max_sources = max(1, max_sources)
        self.max_search_rounds = max(1, max_search_rounds)
        self.use_langgraph = use_langgraph

    async def run(self) -> EventTraceState:
        state: EventTraceState = {
            "topic": self.topic,
            "research_depth": self.research_depth,
            "time_range": self.time_range,
            "focus": self.focus,
            "task_plan": TraceTaskPlan(
                topic=self.topic,
                objective="",
                research_depth=self.research_depth,
                time_range=self.time_range,
                focus=self.focus,
            ),
            "queries": [],
            "candidate_sources": list(self.initial_sources),
            "pages": [],
            "evidences": [],
            "event_clusters": [],
            "timeline": [],
            "validation_notes": [],
            "report": "",
            "search_round": 0,
            "weak_evidence_count": 0,
            "run_id": self.run_recorder.run_id if self.run_recorder else "",
        }
        if self.use_langgraph:
            graph = self._build_langgraph()
            if graph is not None:
                return await graph.ainvoke(state)
        return await self._run_fallback(state)

    def _build_langgraph(self) -> Any | None:
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return None

        graph = StateGraph(EventTraceState)
        graph.add_node("query_planner", self._recorded_node("query_planner", self.query_planner))
        graph.add_node("source_search", self._recorded_node("source_search", self.source_search))
        graph.add_node("page_fetch", self._recorded_node("page_fetch", self.page_fetch))
        graph.add_node("evidence_extract", self._recorded_node("evidence_extract", self.evidence_extract))
        graph.add_node("event_cluster", self._recorded_node("event_cluster", self.event_cluster))
        graph.add_node("timeline_builder", self._recorded_node("timeline_builder", self.timeline_builder))
        graph.add_node("cross_validator", self._recorded_node("cross_validator", self.cross_validator))
        graph.add_node("report_writer", self._recorded_node("report_writer", self.report_writer))

        graph.set_entry_point("query_planner")
        graph.add_edge("query_planner", "source_search")
        graph.add_edge("source_search", "page_fetch")
        graph.add_edge("page_fetch", "evidence_extract")
        graph.add_edge("evidence_extract", "event_cluster")
        graph.add_edge("event_cluster", "timeline_builder")
        graph.add_edge("timeline_builder", "cross_validator")
        graph.add_conditional_edges(
            "cross_validator",
            self._validation_route,
            {"search": "source_search", "write": "report_writer"},
        )
        graph.add_edge("report_writer", END)
        return graph.compile()

    async def _run_fallback(self, state: EventTraceState) -> EventTraceState:
        state = await self._run_recorded("query_planner", self.query_planner, state)
        while True:
            state = await self._run_recorded("source_search", self.source_search, state)
            state = await self._run_recorded("page_fetch", self.page_fetch, state)
            state = await self._run_recorded("evidence_extract", self.evidence_extract, state)
            state = await self._run_recorded("event_cluster", self.event_cluster, state)
            state = await self._run_recorded("timeline_builder", self.timeline_builder, state)
            state = await self._run_recorded("cross_validator", self.cross_validator, state)
            if self._validation_route(state) != "search":
                break
        return await self._run_recorded("report_writer", self.report_writer, state)

    def _recorded_node(self, node_name: str, fn: Callable[[EventTraceState], Awaitable[EventTraceState]]):
        async def wrapper(state: EventTraceState) -> EventTraceState:
            return await self._run_recorded(node_name, fn, state)

        return wrapper

    async def _run_recorded(
        self,
        node_name: str,
        fn: Callable[[EventTraceState], Awaitable[EventTraceState]],
        state: EventTraceState,
    ) -> EventTraceState:
        started_at = time.perf_counter()
        try:
            next_state = await fn(state)
        except Exception as exc:
            if self.run_recorder:
                self.run_recorder.record_node(node_name, state, started_at, error=str(exc))
            raise
        if self.run_recorder:
            self.run_recorder.record_node(node_name, next_state, started_at)
            if node_name == "report_writer":
                self.run_recorder.write_report(next_state.get("report", ""))
        return next_state

    async def query_planner(self, state: EventTraceState) -> EventTraceState:
        topic = state["topic"]
        task_plan = await self.task_planner.plan(topic)
        state["task_plan"] = task_plan
        state["queries"] = list(dict.fromkeys(task_plan.search_queries))
        return state

    async def source_search(self, state: EventTraceState) -> EventTraceState:
        existing = {source.url for source in state.get("candidate_sources", [])}
        sources = list(state.get("candidate_sources", []))
        search_round = state.get("search_round", 0)
        queries = state.get("queries", [])
        query = queries[min(search_round, len(queries) - 1)] if queries else state["topic"]
        remaining = max(0, self.max_sources - len(sources))

        if remaining:
            try:
                found = await self.search_provider(query, remaining)
            except Exception as exc:
                found = []
                state.setdefault("validation_notes", []).append(
                    ValidationNote(
                        target=query[:120],
                        status="warning",
                        message=f"Search failed and was skipped: {exc}",
                    )
                )
            for source in found:
                if source.url and source.url not in existing:
                    sources.append(source)
                    existing.add(source.url)
                    if len(sources) >= self.max_sources:
                        break

        state["candidate_sources"] = sources[: self.max_sources]
        state["search_round"] = search_round + 1
        return state

    async def page_fetch(self, state: EventTraceState) -> EventTraceState:
        fetched = {page.url for page in state.get("pages", [])}
        new_sources = [source for source in state.get("candidate_sources", []) if source.url not in fetched]
        if new_sources:
            pages = await asyncio.gather(*(self.fetch_provider(source) for source in new_sources))
            state["pages"] = state.get("pages", []) + list(pages)
        return state

    async def evidence_extract(self, state: EventTraceState) -> EventTraceState:
        evidences = []
        for page in state.get("pages", []):
            evidences.extend(await self.evidence_extractor(page))

        seen = set()
        unique = []
        for evidence in evidences:
            key = (evidence.source_url, evidence.claim)
            if key in seen:
                continue
            seen.add(key)
            unique.append(evidence)
        state["evidences"] = unique
        return state

    async def event_cluster(self, state: EventTraceState) -> EventTraceState:
        clusters: list[EventCluster] = []
        for evidence in state.get("evidences", []):
            target = None
            for cluster in clusters:
                same_time = evidence.event_time == cluster.event_time and evidence.event_time != "unknown"
                similar = _overlap_score(evidence.claim, cluster.summary) >= 0.28
                if same_time or similar:
                    target = cluster
                    break
            if target is None:
                target = EventCluster(
                    event_time=evidence.event_time,
                    summary=evidence.claim,
                    actor=evidence.actor,
                    evidences=[],
                    source_urls=[],
                )
                clusters.append(target)
            target.evidences.append(evidence)
            if evidence.source_url not in target.source_urls:
                target.source_urls.append(evidence.source_url)

        for cluster in clusters:
            cluster.confidence = min(1.0, sum(e.confidence for e in cluster.evidences) / max(1, len(cluster.evidences)))
        state["event_clusters"] = clusters
        return state

    async def timeline_builder(self, state: EventTraceState) -> EventTraceState:
        def sort_key(item: EventCluster) -> tuple[int, str]:
            return (1 if item.event_time == "unknown" else 0, item.event_time)

        timeline = [
            TimelineItem(
                event_time=cluster.event_time,
                summary=cluster.summary,
                citations=cluster.source_urls,
                confidence=cluster.confidence,
                validation_status=cluster.validation_status,
            )
            for cluster in sorted(state.get("event_clusters", []), key=sort_key)
        ]
        state["timeline"] = timeline
        return state

    async def cross_validator(self, state: EventTraceState) -> EventTraceState:
        notes = []
        weak_count = 0
        for cluster in state.get("event_clusters", []):
            supported_evidences = []
            unsupported_count = 0
            for evidence in cluster.evidences:
                judgment = await self.citation_judge.judge(evidence)
                if judgment.status == "unsupported":
                    evidence.validation_status = "unsupported"
                    unsupported_count += 1
                elif judgment.status == "unclear":
                    evidence.validation_status = "unclear"
                else:
                    evidence.validation_status = "supported_by_quote"
                    supported_evidences.append(evidence)

            supported_urls = {evidence.source_url for evidence in supported_evidences}
            conflict_note = self.conflict_detector.detect(supported_evidences)
            if conflict_note:
                cluster.validation_status = "conflicted"
                status = "conflicted"
                message = conflict_note.message
                weak_count += 1
            elif len(supported_urls) >= 2:
                cluster.validation_status = "supported"
                status = "supported"
                message = f"{len(supported_urls)} independent source URLs support this event."
            elif not supported_evidences and unsupported_count:
                cluster.validation_status = "unsupported"
                status = "unsupported"
                message = "No quote clearly supports this event claim."
                weak_count += 1
            else:
                cluster.validation_status = "single_source"
                status = "weak"
                message = "Only one source URL clearly supports this event."
                weak_count += 1
            for evidence in supported_evidences:
                evidence.validation_status = cluster.validation_status
            notes.append(ValidationNote(target=cluster.summary[:120], status=status, message=message))

        state["validation_notes"] = notes
        state["weak_evidence_count"] = weak_count
        sorted_clusters = sorted(
            state.get("event_clusters", []),
            key=lambda item: (1 if item.event_time == "unknown" else 0, item.event_time),
        )
        state["timeline"] = [
            TimelineItem(
                event_time=cluster.event_time,
                summary=cluster.summary,
                citations=cluster.source_urls,
                confidence=cluster.confidence,
                validation_status=cluster.validation_status,
            )
            for cluster in sorted_clusters
        ]
        if self.memory:
            self.memory.append_evidences(state["topic"], state.get("evidences", []))
        return state

    def _validation_route(self, state: EventTraceState) -> str:
        has_no_sources = not state.get("candidate_sources")
        has_no_evidence = not state.get("evidences")
        can_search_more = state.get("search_round", 0) < self.max_search_rounds
        if can_search_more and (has_no_sources or has_no_evidence):
            return "search"
        return "write"

    async def report_writer(self, state: EventTraceState) -> EventTraceState:
        if state.get("research_depth") == "deep":
            return await self._deep_report_writer(state)

        reference_urls = []
        for source in state.get("candidate_sources", []):
            if source.url not in reference_urls:
                reference_urls.append(source.url)
        reference_index = {url: idx + 1 for idx, url in enumerate(reference_urls)}

        lines = [
            f"# Event Trace Report: {state['topic']}",
            "",
            "## Summary",
            self._summary_line(state),
            "",
            "## Task Plan",
        ]
        task_plan = state.get("task_plan")
        if task_plan:
            lines.extend(
                [
                    f"- Objective: {task_plan.objective}",
                    f"- Search queries: {', '.join(task_plan.search_queries)}",
                    f"- Required questions: {'; '.join(task_plan.required_questions)}",
                    f"- Validation rules: {'; '.join(task_plan.validation_rules)}",
                ]
            )
            if task_plan.memory_hints:
                lines.append(f"- Memory hints: {'; '.join(task_plan.memory_hints)}")
        else:
            lines.append("- No explicit task plan was generated.")

        lines.extend(
            [
                "",
                "## Timeline",
            ]
        )
        timeline = state.get("timeline", [])
        if not timeline:
            lines.append("- No structured events were extracted from the available sources.")
        for item in timeline:
            citations = " ".join(f"[{reference_index[url]}]" for url in item.citations if url in reference_index)
            lines.append(
                f"- {item.event_time}: {item.summary} {citations} "
                f"(status: {item.validation_status}, confidence: {item.confidence:.2f})"
            )

        lines.extend(["", "## Key Evidence"])
        for idx, cluster in enumerate(state.get("event_clusters", []), 1):
            lines.append(f"### Event {idx}")
            lines.append(f"- Conclusion: {cluster.summary}")
            lines.append(f"- Status: {cluster.validation_status}")
            lines.append(f"- Sources: {', '.join(cluster.source_urls) if cluster.source_urls else 'none'}")
            for evidence in cluster.evidences[:3]:
                lines.append(f"- Quote: {evidence.quote}")
            lines.append("")

        lines.extend(["## Cross Validation"])
        for note in state.get("validation_notes", []):
            lines.append(f"- {note.status}: {note.message} Target: {note.target}")

        lines.extend(["", "## Gaps And Uncertainties"])
        weak = [note for note in state.get("validation_notes", []) if note.status != "supported"]
        if weak:
            lines.append("- Some events are supported by only one source and should be treated as provisional.")
        else:
            lines.append("- No single-source events were detected.")

        lines.extend(["", "## References"])
        for source in state.get("candidate_sources", []):
            if source.url in reference_index:
                label = source.title or source.url
                lines.append(f"- [{reference_index[source.url]}] {label}: {source.url}")

        state["report"] = "\n".join(lines).strip() + "\n"
        return state

    async def _deep_report_writer(self, state: EventTraceState) -> EventTraceState:
        reference_urls = []
        for source in state.get("candidate_sources", []):
            if source.url not in reference_urls:
                reference_urls.append(source.url)
        reference_index = {url: idx + 1 for idx, url in enumerate(reference_urls)}
        timeline = state.get("timeline", [])
        weak = [note for note in state.get("validation_notes", []) if note.status != "supported"]
        supported = [item for item in timeline if item.validation_status == "supported"]
        conflicted = [item for item in timeline if item.validation_status == "conflicted"]
        single_source = [item for item in timeline if item.validation_status == "single_source"]
        unsupported = [item for item in timeline if item.validation_status == "unsupported"]

        lines = [
            f"# Event Deep Research Report: {state['topic']}",
            "",
            "## Executive Summary",
            self._summary_line(state),
            f"- Timeline items: {len(timeline)}",
            f"- Supported: {len(supported)}",
            f"- Single-source: {len(single_source)}",
            f"- Conflicted: {len(conflicted)}",
            f"- Unsupported: {len(unsupported)}",
            "",
            "## Scope and Method",
        ]
        task_plan = state.get("task_plan")
        if task_plan:
            lines.extend(
                [
                    f"- Research depth: {task_plan.research_depth}",
                    f"- Time range: {task_plan.time_range or 'not specified'}",
                    f"- Focus: {', '.join(task_plan.focus) if task_plan.focus else 'not specified'}",
                    f"- Objective: {task_plan.objective}",
                    f"- Search queries: {', '.join(task_plan.search_queries)}",
                    f"- Source strategy: {'; '.join(task_plan.source_strategy)}",
                    f"- Validation rules: {'; '.join(task_plan.validation_rules)}",
                ]
            )
        else:
            lines.append("- No explicit task plan was generated.")

        lines.extend(["", "## Key Timeline"])
        if not timeline:
            lines.append("- No structured events were extracted from the available sources.")
        for item in timeline:
            citations = " ".join(f"[{reference_index[url]}]" for url in item.citations if url in reference_index)
            lines.append(
                f"- {item.event_time}: {item.summary} {citations} "
                f"(status: {item.validation_status}, confidence: {item.confidence:.2f})"
            )

        lines.extend(["", "## Phase Analysis"])
        phase_groups: dict[str, list[TimelineItem]] = {}
        for item in timeline:
            phase = item.event_time[:7] if item.event_time and item.event_time != "unknown" else "unknown"
            phase_groups.setdefault(phase, []).append(item)
        if not phase_groups:
            lines.append("- No phases could be derived from the extracted timeline.")
        for phase, items in phase_groups.items():
            lines.append(f"### {phase}")
            for item in items[:5]:
                lines.append(f"- {item.summary} (status: {item.validation_status})")

        lines.extend(["", "## Evidence Table"])
        lines.append("| Time | Claim | Status | Sources | Quote |")
        lines.append("| --- | --- | --- | --- | --- |")
        for cluster in state.get("event_clusters", []):
            quote = cluster.evidences[0].quote if cluster.evidences else ""
            citations = " ".join(f"[{reference_index[url]}]" for url in cluster.source_urls if url in reference_index)
            lines.append(
                f"| {cluster.event_time} | {cluster.summary} | {cluster.validation_status} | "
                f"{citations or 'none'} | {quote[:180]} |"
            )

        lines.extend(["", "## Conflicts and Unverified Claims"])
        if weak:
            for note in weak:
                lines.append(f"- {note.status}: {note.message} Target: {note.target}")
        else:
            lines.append("- No conflicted, single-source, or unsupported claims were detected.")

        lines.extend(["", "## Source Quality Notes"])
        source_types: dict[str, int] = {}
        for source in state.get("candidate_sources", []):
            source_types[source.source_type] = source_types.get(source.source_type, 0) + 1
        if source_types:
            for source_type, count in sorted(source_types.items()):
                lines.append(f"- {source_type}: {count} source(s)")
        else:
            lines.append("- No candidate sources were collected.")
        lines.append("- Treat official or primary documents as stronger evidence than secondary commentary when available.")

        lines.extend(["", "## Open Questions"])
        if weak:
            lines.append("- Which single-source claims can be corroborated by independent official or primary sources?")
            lines.append("- Do conflicting accounts disagree on timing, actor, action, or outcome?")
            lines.append("- Are there missing official responses, regulator records, court filings, or primary documents?")
        else:
            lines.append("- Continue monitoring for later corrections, official updates, and newly released primary documents.")

        lines.extend(["", "## References"])
        for source in state.get("candidate_sources", []):
            if source.url in reference_index:
                label = source.title or source.url
                lines.append(f"- [{reference_index[source.url]}] {label}: {source.url}")

        state["report"] = "\n".join(lines).strip() + "\n"
        return state

    def _summary_line(self, state: EventTraceState) -> str:
        event_count = len(state.get("event_clusters", []))
        source_count = len(state.get("candidate_sources", []))
        weak_count = state.get("weak_evidence_count", 0)
        return (
            f"Collected {source_count} candidate sources, extracted {event_count} event clusters, "
            f"and found {weak_count} single-source or weakly supported events."
        )


@dataclass
class EventTraceEvalCase:
    """Closed-set event trace evaluation sample."""

    topic: str
    sources: list[str] = field(default_factory=list)
    required_events: list[str] = field(default_factory=list)
    expected_citations: list[str] = field(default_factory=list)


@dataclass
class EventTraceEvalResult:
    """Event trace evaluation metrics."""

    citation_coverage: float
    unsupported_claim_rate: float
    required_event_recall: float
    total_events: int
    total_evidences: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventTraceEvalHarness:
    """Evaluate an event trace state against a closed-set sample."""

    def evaluate_state(self, state: EventTraceState, case: EventTraceEvalCase) -> EventTraceEvalResult:
        timeline = state.get("timeline", [])
        evidences = state.get("evidences", [])

        cited_events = sum(1 for item in timeline if item.citations)
        citation_coverage = cited_events / len(timeline) if timeline else 0.0

        unsupported = sum(1 for evidence in evidences if evidence.validation_status == "unsupported")
        unsupported_claim_rate = unsupported / len(evidences) if evidences else 0.0

        matched_required = 0
        summaries = [item.summary for item in timeline]
        for required_event in case.required_events:
            if any(_overlap_score(required_event, summary) >= 0.25 for summary in summaries):
                matched_required += 1
        required_event_recall = matched_required / len(case.required_events) if case.required_events else 1.0

        return EventTraceEvalResult(
            citation_coverage=citation_coverage,
            unsupported_claim_rate=unsupported_claim_rate,
            required_event_recall=required_event_recall,
            total_events=len(timeline),
            total_evidences=len(evidences),
        )


def state_to_jsonable(state: EventTraceState) -> dict[str, Any]:
    """Convert an event trace state into JSON-serializable data."""

    result: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, list):
            result[key] = [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in value]
        elif hasattr(value, "__dataclass_fields__"):
            result[key] = asdict(value)
        else:
            result[key] = value
    return result
