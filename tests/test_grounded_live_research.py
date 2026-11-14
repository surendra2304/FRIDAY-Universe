"""Extractive relevance regressions. Fixtures are not live acceptance evidence."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

spec = importlib.util.spec_from_file_location('research_relevance', Path(__file__).resolve().parents[1] / 'IntelX/intelx/api/live_research_task.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def collect(query, paragraphs):
    url = 'https://example.org/doc'
    search = SimpleNamespace(fetch=AsyncMock(return_value=[SimpleNamespace(url=url, title='Fixture')]))
    document = '<html>' + ''.join('<p>' + p + '</p>' for p in paragraphs) + '</html>'
    fetch = SimpleNamespace(fetch=AsyncMock(return_value=SimpleNamespace(status_code=200, content_type='text/html', final_url=url, content=document.encode())))
    return asyncio.run(m.collect_live_brief(query, search, fetch))


def test_unrelated_retrieved_prose_is_not_a_successful_topic_brief():
    result = collect('quantum coherence time', ['The orchard produced excellent apples during the recent summer harvest.'])
    assert result['status'] == 'DEGRADED'
    assert not result['findings']


def test_long_overview_does_not_truncate_quoted_comma_evidence():
    overview = ('The CSV format uses a module for CSV reader and writer objects and DictReader data. ' * 12).strip()
    quote = 'A one-character string used to quote fields containing special characters, such as the delimiter or the quotechar, or which contain new-line characters.'
    result = collect('Explain how DictReader handles quoted commas and how JSON serialization works.', [overview, quote])
    assert any('quote fields containing special characters' in f['quote'] for f in result['findings'])
    assert all(f['quote'] in [overview, quote] for f in result['findings'])


def test_noncontiguous_source_passages_are_not_one_verbatim_quote():
    passages = ['Battery capacity is measured in ampere-hours according to this fixture source.', 'Battery temperature is recorded separately in this explicitly synthetic fixture.']
    result = collect('battery capacity temperature', passages)
    assert len(result['findings']) == 2
    assert all(f['quote'] in passages for f in result['findings'])


def test_relevance_is_not_claimed_as_answer_verification():
    result = collect('battery capacity', ['Battery capacity is measured in ampere-hours according to this fixture source.'])
    assert result['answer_kind'] == 'source_excerpts'
    assert result['question_answered'] is False
    assert result['sources'][0]['independently_verified'] is False


def test_each_of_multiple_passages_keeps_its_own_source_citation():
    urls = ['https://example.org/one', 'https://example.org/two']
    search = SimpleNamespace(fetch=AsyncMock(return_value=[SimpleNamespace(url=u, title=u) for u in urls]))
    async def fetched(url, **kwargs):
        sentences = ['Battery capacity is measured in this separately cited fixture document.', 'Battery temperature is also measured in a separate sentence within this document.']
        return SimpleNamespace(status_code=200, content_type='text/html', final_url=url, content=(''.join('<p>'+s+'</p>' for s in sentences)).encode())
    result = asyncio.run(m.collect_live_brief('battery capacity temperature', search, SimpleNamespace(fetch=fetched)))
    assert len(result['findings']) == 4
    assert [f['citations'][0]['source_url'] for f in result['findings']] == [urls[0], urls[0], urls[1], urls[1]]
    assert all(f['citations'][0]['source_url'] in result['text_response'] for f in result['findings'])


def test_truncated_quote_is_explicitly_a_contiguous_source_prefix():
    passage = ('Battery capacity is measured and recorded repeatedly in this fixture. ' * 25).strip()
    result = collect('battery capacity', [passage])
    finding = result['findings'][0]
    assert finding['truncated'] is True
    assert finding['quote'] == passage[:1200]


def test_duplicate_paragraphs_do_not_consume_all_three_evidence_slots():
    first = 'Battery capacity is measured in ampere-hours according to this fixture source.'
    second = 'Battery temperature is measured separately according to this fixture source.'
    result = collect('battery capacity temperature', [first, first, first, second])
    assert len(result['findings']) == 2


def test_generic_citation_instructions_do_not_make_csv_relevant_to_qubits():
    paragraphs = [
        'Instructs writer objects to only quote those fields which contain special characters such as delimiter or quotechar.',
        'A read-only description of the dialect in use by the parser.',
    ]
    result = collect('Explain quantum coherence time and superconducting qubit fidelity. Cite only directly relevant passages.', paragraphs)
    assert result['status'] == 'DEGRADED'
    assert result['findings'] == []
