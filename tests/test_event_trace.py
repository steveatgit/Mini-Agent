import json
import socket

import pytest

from mini_agent.event_trace import (
    CitationJudge,
    DefaultPageFetcher,
    EventTraceAgent,
    EventTraceEvalCase,
    EventTraceEvalHarness,
    EventTraceMemory,
    EventTraceRunRecorder,
    Evidence,
    LLMEvidenceExtractor,
    NetworkPolicy,
    Page,
    ResponsibleTaskPlanner,
    Source,
    state_to_jsonable,
)
from mini_agent.schema import LLMResponse


class FakePlannerLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    async def generate(self, messages, tools=None):
        self.calls += 1
        return LLMResponse(content=self.content, finish_reason="stop")


@pytest.mark.asyncio
async def test_event_trace_agent_runs_from_local_sources(tmp_path):
    source_a = tmp_path / "source_a.txt"
    source_a.write_text(
        "2024-01-01 Acme reported a product outage after users could not log in. "
        "2024-01-02 Acme published an official response and said the service was restored.",
        encoding="utf-8",
    )
    source_b = tmp_path / "source_b.txt"
    source_b.write_text(
        "2024-01-01 Customers reported that Acme login service was unavailable. "
        "2024-01-03 A regulator said it was reviewing the Acme outage response.",
        encoding="utf-8",
    )

    memory = EventTraceMemory(tmp_path / "memory.jsonl")
    agent = EventTraceAgent(
        topic="Acme product outage",
        initial_sources=[
            Source(url=str(source_a), title="Source A"),
            Source(url=str(source_b), title="Source B"),
        ],
        memory=memory,
        use_langgraph=False,
    )

    state = await agent.run()

    assert state["candidate_sources"]
    assert state["task_plan"].objective
    assert "official response" in " ".join(state["task_plan"].search_queries)
    assert len(state["pages"]) == 2
    assert state["evidences"]
    assert state["event_clusters"]
    assert state["timeline"]
    timeline_statuses = {item.validation_status for item in state["timeline"]}
    assert "unverified" not in timeline_statuses
    assert "supported" in timeline_statuses
    assert "# Event Trace Report: Acme product outage" in state["report"]
    assert "## Task Plan" in state["report"]
    assert "## References" in state["report"]
    assert "[1] Source A" in state["report"]
    assert memory.memory_file.exists()


@pytest.mark.asyncio
async def test_event_trace_retries_search_when_no_evidence():
    calls = []

    async def search_provider(query: str, max_results: int):
        calls.append((query, max_results))
        return []

    agent = EventTraceAgent(
        topic="missing event",
        search_provider=search_provider,
        max_search_rounds=2,
        use_langgraph=False,
    )

    state = await agent.run()

    assert len(calls) == 2
    assert calls[0][0] == "missing event"
    assert calls[1][0] == "missing event timeline"
    assert state["report"]
    assert "No structured events" in state["report"]


def test_event_trace_state_to_jsonable_handles_dataclasses(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("2025-05-01 Example event happened.", encoding="utf-8")

    state = {
        "topic": "Example",
        "candidate_sources": [Source(url=str(source), title="Example source")],
        "report": "ok",
    }

    data = state_to_jsonable(state)

    assert data["candidate_sources"][0]["title"] == "Example source"
    json.dumps(data)


@pytest.mark.asyncio
async def test_network_policy_allows_proxy_fake_ip_for_domain(monkeypatch):
    def fake_getaddrinfo(hostname, port):
        assert hostname == "example.com"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("198.18.1.109", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    await NetworkPolicy().validate_url("https://example.com/article")


@pytest.mark.asyncio
async def test_network_policy_blocks_direct_proxy_fake_ip(monkeypatch):
    def fake_getaddrinfo(hostname, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (hostname, 80))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError, match="Blocked private or non-public address"):
        await NetworkPolicy().validate_url("http://198.18.1.109/article")


@pytest.mark.asyncio
async def test_responsible_task_planner_uses_llm_and_keeps_rule_baseline():
    llm = FakePlannerLLM(
        json.dumps(
            {
                "objective": "Trace Acme incident with official and regulator evidence.",
                "search_queries": ["Acme regulator investigation", "Acme customer impact"],
                "required_questions": ["What did the regulator say?"],
                "source_strategy": ["Prioritize regulator records."],
                "evidence_requirements": ["Keep docket or filing URL when present."],
                "validation_rules": ["regulator_supported: supported by a regulator record."],
                "safety_constraints": ["Do not fetch private portals."],
            }
        )
    )
    planner = ResponsibleTaskPlanner(llm_client=llm)

    plan = await planner.plan("Acme outage")

    assert llm.calls == 1
    assert "Acme outage" in plan.search_queries
    assert "Acme regulator investigation" in plan.search_queries
    assert "supported: at least two source URLs support the event cluster." in plan.validation_rules
    assert "Do not fetch private, localhost, or internal network URLs." in plan.safety_constraints


@pytest.mark.asyncio
async def test_responsible_task_planner_falls_back_on_invalid_llm_output():
    planner = ResponsibleTaskPlanner(llm_client=FakePlannerLLM("not json"))

    plan = await planner.plan("Acme outage")

    assert plan.objective.startswith("Build a cited event trace")
    assert plan.search_queries[:2] == ["Acme outage", "Acme outage timeline"]


@pytest.mark.asyncio
async def test_responsible_task_planner_falls_back_on_invalid_schema():
    planner = ResponsibleTaskPlanner(llm_client=FakePlannerLLM(json.dumps(["not", "an", "object"])))

    plan = await planner.plan("Acme outage")

    assert plan.objective.startswith("Build a cited event trace")
    assert "Acme outage official response" in plan.search_queries


@pytest.mark.asyncio
async def test_responsible_task_planner_deep_mode_uses_scope_and_focus():
    planner = ResponsibleTaskPlanner(
        research_depth="deep",
        time_range="2024-01 to 2024-03",
        focus=["official response", "regulator review"],
    )

    plan = await planner.plan("Acme outage")

    joined_queries = " ".join(plan.search_queries)
    assert plan.research_depth == "deep"
    assert plan.time_range == "2024-01 to 2024-03"
    assert plan.focus == ["official response", "regulator review"]
    assert "2024-01 to 2024-03" in joined_queries
    assert "official response" in joined_queries
    assert "regulator review" in joined_queries
    assert "disputed claims" in joined_queries


@pytest.mark.asyncio
async def test_llm_evidence_extractor_validates_schema_and_falls_back():
    extractor = LLMEvidenceExtractor(FakePlannerLLM(json.dumps([{"claim": ""}, {"confidence": 2.0}])))

    evidences = await extractor(Page(url="local", title="Local", text="2024-01-01 Acme reported a verified outage."))

    assert evidences
    assert evidences[0].claim.startswith("2024-01-01 Acme")


@pytest.mark.asyncio
async def test_network_policy_blocks_localhost():
    policy = NetworkPolicy()

    with pytest.raises(ValueError, match="Blocked hostname"):
        await policy.validate_url("http://localhost:8000/private")


@pytest.mark.asyncio
async def test_page_fetcher_reads_cached_http_page(tmp_path):
    cache_dir = tmp_path / "cache"
    fetcher = DefaultPageFetcher(cache_dir=cache_dir)
    cached = {
        "url": "https://example.com/story",
        "title": "Cached Story",
        "text": "2024-01-01 Cached event text.",
        "published_at": "2024-01-01",
        "author": None,
        "fetched_at": "2024-01-01T00:00:00Z",
        "error": None,
    }
    cache_path = fetcher._cache_path(cached["url"])
    assert cache_path is not None
    cache_path.write_text(json.dumps(cached), encoding="utf-8")

    page = await fetcher(Source(url=cached["url"], title="Network title"))

    assert page.title == "Cached Story"
    assert page.text == "2024-01-01 Cached event text."


@pytest.mark.asyncio
async def test_citation_judge_uses_llm_when_available():
    judge = CitationJudge(llm_client=FakePlannerLLM(json.dumps({"status": "unsupported", "reason": "quote does not mention outage"})))
    evidence = Evidence(
        event_time="2024-01-01",
        actor="Acme",
        action="reported",
        claim="Acme reported an outage.",
        quote="Acme launched a new product.",
        source_url="local",
    )

    judgment = await judge.judge(evidence)

    assert judgment.status == "unsupported"
    assert "quote" in judgment.reason


@pytest.mark.asyncio
async def test_cross_validator_marks_unsupported_claims():
    evidence = Evidence(
        event_time="2024-01-01",
        actor="Acme",
        action="reported",
        claim="Acme reported an outage.",
        quote="Completely unrelated sentence.",
        source_url="local",
    )
    agent = EventTraceAgent(topic="Acme outage", initial_sources=[Source(url="local")], use_langgraph=False)
    state = {
        "topic": "Acme outage",
        "event_clusters": [],
        "evidences": [evidence],
        "timeline": [],
        "validation_notes": [],
    }

    state = await agent.event_cluster(state)
    state = await agent.cross_validator(state)

    assert state["event_clusters"][0].validation_status == "unsupported"
    assert evidence.validation_status == "unsupported"


def test_event_trace_eval_harness_scores_state():
    evidence_a = Evidence(
        event_time="2024-01-01",
        actor="Acme",
        action="reported",
        claim="Acme reported an outage.",
        quote="Acme reported an outage.",
        source_url="source-a",
        validation_status="single_source",
    )
    evidence_b = Evidence(
        event_time="2024-01-02",
        actor="Acme",
        action="reported",
        claim="Acme denied an outage.",
        quote="Unrelated quote.",
        source_url="source-b",
        validation_status="unsupported",
    )
    state = {
        "timeline": [
            type("Timeline", (), {"summary": "Acme reported an outage.", "citations": ["source-a"]})(),
            type("Timeline", (), {"summary": "Acme denied an outage.", "citations": []})(),
        ],
        "evidences": [evidence_a, evidence_b],
    }

    result = EventTraceEvalHarness().evaluate_state(
        state,
        EventTraceEvalCase(topic="Acme outage", required_events=["Acme reported outage"]),
    )

    assert result.citation_coverage == 0.5
    assert result.unsupported_claim_rate == 0.5
    assert result.required_event_recall == 1.0


@pytest.mark.asyncio
async def test_cross_validator_marks_conflicted_claims():
    evidence_a = Evidence(
        event_time="2024-01-01",
        actor="Acme",
        action="confirmed",
        claim="Acme confirmed an outage.",
        quote="Acme confirmed an outage.",
        source_url="source-a",
    )
    evidence_b = Evidence(
        event_time="2024-01-01",
        actor="Acme",
        action="denied",
        claim="Acme denied an outage.",
        quote="Acme denied an outage.",
        source_url="source-b",
    )
    agent = EventTraceAgent(topic="Acme outage", initial_sources=[Source(url="source-a"), Source(url="source-b")], use_langgraph=False)
    state = {
        "topic": "Acme outage",
        "event_clusters": [],
        "evidences": [evidence_a, evidence_b],
        "timeline": [],
        "validation_notes": [],
    }

    state = await agent.event_cluster(state)
    state = await agent.cross_validator(state)

    assert state["event_clusters"][0].validation_status == "conflicted"
    assert any(note.status == "conflicted" for note in state["validation_notes"])


@pytest.mark.asyncio
async def test_event_trace_run_recorder_persists_state_report_and_audit(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("2024-01-01 Acme reported an outage.", encoding="utf-8")
    recorder = EventTraceRunRecorder(tmp_path / "runs" / "run-1", run_id="run-1")
    agent = EventTraceAgent(
        topic="Acme outage",
        initial_sources=[Source(url=str(source), title="Source")],
        run_recorder=recorder,
        use_langgraph=False,
    )

    state = await agent.run()

    assert state["run_id"] == "run-1"
    assert recorder.state_file.exists()
    assert recorder.report_file.exists()
    assert recorder.audit_file.exists()
    state_data = json.loads(recorder.state_file.read_text(encoding="utf-8"))
    assert state_data["run_id"] == "run-1"
    audit_lines = recorder.audit_file.read_text(encoding="utf-8").splitlines()
    assert any('"node": "query_planner"' in line for line in audit_lines)
    assert any('"node": "report_writer"' in line for line in audit_lines)
