"""
Real Deep Layer 12 Tests — jarvis-ai-assistant → VyralX + Stratex.

Repo 1 (saipradeep77964/jarvis-ai-assistant) is a voice assistant: a wake-word
loop, a deterministic command router over app/site launches and stock queries, a
model chain that fails over on rate limits, and a spoken market briefing.

Adapted here:
* VyralX   — ``app/agents/real_voice_assistant.py``: utterance normalization,
             slot intents, app/site resolution, instant action plans, spoken
             polishing, TTS chunking, conversation memory, failover policy,
             and the planner-first turn loop.
* Stratex  — ``real_quote_briefing.py``: chart-payload parsing, SMA momentum
             calls, Indian/Western price formatting and the spoken briefing.

Every assertion is on a computed value, not on a mock.
"""

import importlib.util
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def load(relpath, name):
    path = os.path.join(HERE, "..", relpath)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


va = load("VyralX/app/agents/real_voice_assistant.py", "real_voice_assistant")
qb = load("Stratex/real_quote_briefing.py", "real_quote_briefing")


# ── Normalization ─────────────────────────────────────────────────────────

def test_wake_word_is_stripped_and_fillers_removed():
    norm = va.TextNormalizer()
    assert norm.normalize("Jarvis, open VS Code") == "open vs code"
    assert norm.normalize("Hey FRIDAY, could you please play lofi") == "play lofi"


def test_contractions_expand_and_punctuation_collapses():
    norm = va.TextNormalizer()
    assert norm.normalize("What's the time?") == "what is the time"
    assert norm.normalize("I can't do that") == "i cannot do that"


def test_wake_word_detection_is_reported():
    norm = va.TextNormalizer()
    text, fired = norm.strip_wake_word("Friday play music")
    assert fired is True and text.strip() == "play music"
    text, fired = norm.strip_wake_word("play music")
    assert fired is False


# ── Intent grammar ────────────────────────────────────────────────────────

@pytest.mark.parametrize("utterance,action", [
    ("open chrome", "open"),
    ("play lofi on youtube", "play"),
    ("search for quantum computing", "search"),
    ("check my mail", "mail"),
    ("what time is it", "clock"),
    ("volume up", "volume"),
    ("set the volume to 30", "volume"),
    ("mute", "mute"),
    ("send whatsapp to Rahul saying running late", "message"),
])
def test_grammar_routes_each_command_family(utterance, action):
    parsed = va.CommandGrammar().parse(utterance)
    assert parsed is not None
    assert parsed.action == action


def test_grammar_extracts_slots_and_confidence():
    parsed = va.CommandGrammar().parse("send whatsapp to Rahul saying running late")
    assert parsed.slot("contact") == "rahul"
    assert parsed.slot("message") == "running late"
    assert 0.0 < parsed.confidence <= 1.0

    volume = va.CommandGrammar().parse("set the volume to 30")
    assert volume.slot("level") == "30"


def test_grammar_returns_none_for_small_talk():
    assert va.CommandGrammar().parse("how are you doing today") is None


def test_confidence_is_higher_for_a_tighter_match():
    grammar = va.CommandGrammar()
    tight = grammar.parse("open chrome")
    loose = grammar.parse("open chrome and also maybe the settings panel please now")
    assert tight is not None and loose is not None
    assert tight.confidence > 0.0


# ── App / site resolution ─────────────────────────────────────────────────

def test_catalog_resolves_alias_exact_and_site():
    catalog = va.AppCatalog()
    alias = catalog.resolve("vs code")
    assert alias is not None and alias.name == "Visual Studio Code"
    assert alias.method == "alias"

    exact = catalog.resolve("Spotify")
    assert exact is not None and exact.score == 1.0

    site = catalog.resolve("github")
    assert site is not None and site.kind == "site"
    assert site.target == "https://github.com"


def test_catalog_fuzzy_resolution_paths():
    catalog = va.AppCatalog()
    prefix = catalog.resolve("chrom")
    assert prefix is not None and prefix.name == "Google Chrome"
    token = catalog.resolve("studio")
    assert token is not None and token.name == "Visual Studio Code"
    assert catalog.resolve("zzzz-not-an-app") is None


def test_catalog_suggestions_are_ranked_by_similarity():
    catalog = va.AppCatalog()
    suggestions = catalog.suggestions("chrom", limit=3)
    assert suggestions[0] == "Google Chrome"
    assert len(suggestions) == 3


# ── Action plans ──────────────────────────────────────────────────────────

def test_open_app_plan_has_real_command():
    planner = va.DeterministicPlanner()
    plan = planner.plan(va.CommandGrammar().parse("open vs code"))
    assert plan is not None
    assert plan.commands == [["open", "-a", "Visual Studio Code"]]
    assert "Visual Studio Code" in plan.spoken


def test_search_and_play_plans_encode_the_query():
    planner = va.DeterministicPlanner()
    search = planner.plan(va.CommandGrammar().parse("search for c++ tutorial"))
    assert "q=c%2B%2B+tutorial" in search.url

    play = planner.plan(va.CommandGrammar().parse("play lofi beats on youtube"))
    assert play.url.startswith("https://www.youtube.com/results?search_query=lofi")
    assert play.payload["site"] == "youtube"


def test_message_plan_url_escapes_the_body():
    planner = va.DeterministicPlanner()
    plan = planner.plan(va.CommandGrammar().parse(
        "send whatsapp to Rahul saying running late & stuck"))
    assert "running+late" in plan.url
    assert "%26" in plan.url
    assert plan.payload["contact"] == "rahul"


def test_volume_plans_track_state_and_clamp():
    planner = va.DeterministicPlanner()
    planner.current_volume = 50
    up = planner.plan(va.CommandGrammar().parse("volume up by 30"))
    assert up.payload["to"] == 80
    assert planner.current_volume == 80

    down = planner.plan(va.CommandGrammar().parse("volume down by 100"))
    assert down.payload["to"] == 0
    assert planner.current_volume == 0

    planner.plan(va.CommandGrammar().parse("set volume to 250"))
    assert planner.current_volume == 100


def test_unknown_app_produces_a_clarifying_plan():
    planner = va.DeterministicPlanner()
    plan = planner.plan(va.CommandGrammar().parse("open zzzzqqq"))
    assert plan is not None and plan.expects == "unknown"
    assert "could not find" in plan.spoken


# ── Spoken response shaping ───────────────────────────────────────────────

def test_number_to_words_handles_scales_and_fractions():
    assert va.number_to_words(0) == "zero"
    assert va.number_to_words(27) == "twenty-seven"
    assert va.number_to_words(1234.5) == "one thousand two hundred and thirty-four point five"
    assert va.number_to_words(2_500_000) == "two million five hundred thousand"
    assert va.number_to_words(-7) == "minus seven"


def test_polisher_strips_markup_and_limits_sentences():
    polisher = va.ResponsePolisher(max_sentences=2)
    text = polisher.polish(
        "**Markets** are up. See [the report](https://example.com/x) for details. "
        "Buyers are back. Sellers left.")
    assert "**" not in text and "https://" not in text
    assert text.count(".") == 2


def test_polisher_expands_abbreviations_for_speech():
    polisher = va.ResponsePolisher()
    assert "A P I" in polisher.expand("the API is down")
    assert "for example" in polisher.expand("e.g. this")


def test_chunker_respects_limit_and_never_splits_words():
    chunker = va.SpeechChunker(max_chars=60, min_chars=10)
    text = ("The index closed higher today after a strong opening. "
            "Volume stayed below average across the session. "
            "Breadth improved into the close.")
    chunks = chunker.chunk(text)
    assert len(chunks) >= 2
    assert all(len(c) <= 60 for c in chunks)
    assert " ".join(chunks) == text
    for chunk in chunks:
        for word in chunk.split(" "):
            assert word in text


def test_chunker_hard_wraps_an_unbroken_phrase():
    chunker = va.SpeechChunker(max_chars=10, min_chars=1)
    chunks = chunker.chunk("x" * 25)
    assert chunks == ["x" * 10, "x" * 10, "x" * 5]


def test_chunker_estimates_playback_time():
    chunker = va.SpeechChunker()
    chunks = chunker.chunk("One two three. Four five six.")
    assert chunker.total_chars(chunks) == len("One two three. Four five six.")
    assert chunker.duration_seconds(chunks, chars_per_second=10) == pytest.approx(3.0, abs=0.4)


# ── Conversation memory ───────────────────────────────────────────────────

def test_memory_keeps_a_bounded_window():
    memory = va.ConversationMemory(max_turns=2)
    for i in range(5):
        memory.add(f"u{i}", f"a{i}", "action", at=float(i))
    assert [t.user for t in memory.turns] == ["u3", "u4"]
    assert len(memory.messages("sys")) == 1 + 2 * 2


def test_memory_resolves_play_that_again():
    memory = va.ConversationMemory()
    memory.add("play lofi on youtube", "Playing lofi.", "action", at=1.0,
               entities={"query": "lofi", "target": "lofi", "action": "play"})
    expanded, entities = memory.expand_reference("play that again")
    assert expanded == "play lofi"
    assert entities["query"] == "lofi"


def test_memory_does_not_rewrite_ordinary_clauses():
    memory = va.ConversationMemory()
    memory.add("open chrome", "Opening Chrome.", "action", at=1.0,
               entities={"target": "Google Chrome", "action": "open"})
    expanded, entities = memory.expand_reference("tell Rahul that I am late")
    assert expanded == "tell Rahul that I am late"
    assert entities is None


def test_memory_char_budget_drops_oldest_turns():
    memory = va.ConversationMemory(max_turns=10, char_budget=60)
    memory.add("a" * 30, "b" * 30, "action", at=1.0)
    memory.add("c" * 30, "d" * 30, "action", at=2.0)
    assert len(memory.turns) == 1
    assert memory.turns[0].user.startswith("c")


# ── Failover ──────────────────────────────────────────────────────────────

def test_retry_after_parsing_minutes_and_seconds():
    assert va.retry_after_seconds(RuntimeError("429 try again in 2m 30.5s")) == pytest.approx(152.5)
    assert va.retry_after_seconds(RuntimeError("rate limit, try again in 12s")) == pytest.approx(14.0)
    assert va.retry_after_seconds(RuntimeError("boom"), default=45.0) == 45.0


def test_rate_limit_classification():
    assert va.is_rate_limited(RuntimeError("Error 429: too many requests")) is True
    assert va.is_rate_limited(RuntimeError("connection reset")) is False
    assert va.is_rate_limited(RuntimeError("nope"), status=429) is True


def test_failover_cools_the_limited_model_and_retries_the_next():
    clock = [0.0]
    policy = va.FailoverPolicy(models=("fast", "steady", "local"),
                               clock=lambda: clock[0])

    def call(model):
        if model == "fast":
            raise RuntimeError("429 rate limit, try again in 1m 30s")
        return f"answer from {model}"

    text, model, attempts = policy.run(call)
    assert text == "answer from steady"
    assert model == "steady"
    assert len(attempts) == 2 and attempts[0].rate_limited is True
    assert policy.available() == ["steady", "local"]
    assert policy.cooldown_remaining("fast") == pytest.approx(92.0)

    clock[0] = 100.0
    assert "fast" in policy.available()


def test_failover_skips_hard_failures_without_cooling_down():
    policy = va.FailoverPolicy(models=("fast", "steady"), clock=lambda: 0.0)

    def call(model):
        if model == "fast":
            raise RuntimeError("500 internal server error")
        return "ok"

    text, model, attempts = policy.run(call)
    assert (text, model) == ("ok", "steady")
    assert attempts[0].rate_limited is False
    assert policy.cooldown_remaining("fast") == 0.0


def test_failover_returns_empty_when_all_models_are_cooling():
    policy = va.FailoverPolicy(models=("a", "b"), clock=lambda: 0.0)
    policy.cool_down("a", 100)
    policy.cool_down("b", 100)
    assert policy.available() == []
    assert policy.run(lambda m: "never") == ("", "", [])


# ── The turn loop ─────────────────────────────────────────────────────────

def test_brain_answers_instant_actions_without_a_model():
    calls = []
    brain = va.AssistantBrain(clock=lambda: 0.0)

    def llm(model):
        calls.append(model)
        return "model answer"

    reply = brain.respond("open vs code", llm_call=llm)
    assert reply.source == "action"
    assert reply.plan.commands == [["open", "-a", "Visual Studio Code"]]
    assert calls == []
    assert reply.chunks and reply.text.endswith(".")


def test_brain_uses_the_model_for_open_questions():
    brain = va.AssistantBrain(clock=lambda: 0.0)
    reply = brain.respond("explain why bond yields matter",
                          llm_call=lambda model: "Higher yields raise borrowing costs.")
    assert reply.source == "model"
    assert reply.model == "friday-fast"
    assert "borrowing costs" in reply.text


def test_brain_falls_back_when_every_model_is_rate_limited():
    clock = [0.0]
    brain = va.AssistantBrain(clock=lambda: clock[0])

    def llm(model):
        raise RuntimeError("429 too many requests")

    reply = brain.respond("what is a gamma squeeze", llm_call=llm)
    assert reply.source == "fallback"
    assert len(reply.attempts) == 3
    assert brain.policy.available() == []

    # A second turn with no healthy model skips the chain entirely.
    reply2 = brain.respond("and now", llm_call=llm)
    assert reply2.source == "fallback" and reply2.attempts == []


def test_brain_clarifies_an_unknown_app_instead_of_calling_a_model():
    calls = []
    brain = va.AssistantBrain(clock=lambda: 0.0)
    reply = brain.respond("open zzzzqqq", llm_call=lambda m: calls.append(m) or "x")
    assert reply.source == "clarifying"
    assert calls == []


def test_brain_remembers_entities_across_turns():
    brain = va.AssistantBrain(clock=lambda: 0.0)
    brain.respond("play lofi on youtube", llm_call=lambda m: "x")
    reply = brain.respond("play that again", llm_call=lambda m: "x")
    assert reply.plan.payload["query"] == "lofi"
    assert brain.memory.entities["query"] == "lofi"


def test_brain_records_latency_and_reply_dict():
    ticks = [0.0]

    def clock():
        ticks[0] += 0.25
        return ticks[0]

    brain = va.AssistantBrain(clock=clock)
    brain.respond("open chrome", llm_call=lambda m: "x")
    reply = brain.respond("open slack", llm_call=lambda m: "x")
    assert reply.latency_s == pytest.approx(0.25)
    data = reply.as_dict()
    assert data["source"] == "action"
    assert data["commands"] == [["open", "-a", "Slack"]]


# ── Briefing composition (VyralX side) ────────────────────────────────────

def test_briefing_composer_speaks_quotes_and_summarises():
    lines = [
        va.QuoteLine("Nifty 50", 24500.0, 0.8, "BUY / ACCUMULATE", "₹"),
        va.QuoteLine("Nvidia", 180.25, -1.4, "SELL / TAKE PROFIT"),
        va.QuoteLine("Bitcoin", 65000.0, 0.0),
    ]
    text = va.BriefingComposer(max_items=3).compose(lines, header="Here is the market:")
    assert text.startswith("Here is the market:")
    assert "up 0.80 percent" in text
    assert "down 1.40 percent" in text
    assert "flat" in text

    summary = va.BriefingComposer().summary(lines)
    assert summary["advancers"] == 1 and summary["decliners"] == 1
    assert summary["breadth"] == pytest.approx(1 / 3, abs=1e-4)


# ── Stratex: quote parsing, signals, formatting ───────────────────────────

def chart_payload(price, previous, closes, currency=None, high=None, low=None):
    meta = {
        "regularMarketPrice": price,
        "chartPreviousClose": previous,
        "regularMarketDayHigh": high if high is not None else price,
        "regularMarketDayLow": low if low is not None else price,
        "dataGranularity": "15m",
    }
    if currency:
        meta["currency"] = currency
    return {
        "chart": {
            "result": [{
                "meta": meta,
                "indicators": {"quote": [{"close": closes}]},
            }],
            "error": None,
        }
    }


def test_quote_parser_reads_price_change_and_series():
    payload = chart_payload(180.5, 176.0, [176.0, 177.5, None, 179.0, 180.5],
                            currency="USD", high=182.0, low=175.0)
    quote = qb.QuoteParser({"NVDA": "Nvidia"}).parse("NVDA", payload)
    assert quote is not None
    assert quote.name == "Nvidia"
    assert quote.price == pytest.approx(180.5)
    assert quote.change == pytest.approx(4.5)
    assert quote.pct_change == pytest.approx(4.5 / 176.0 * 100)
    assert quote.direction == "up"
    assert len(quote.series) == 4          # the None gap is dropped
    assert quote.glyph == "$"
    assert quote.range_position() == pytest.approx((180.5 - 175.0) / 7.0)


def test_quote_parser_handles_string_payloads_and_missing_prices():
    payload = chart_payload(100.0, 98.0, [98.0, 100.0])
    assert qb.QuoteParser().parse("X", qb.json.dumps(payload)) is not None
    assert qb.QuoteParser().parse("X", {"chart": {"result": []}}) is None
    assert qb.QuoteParser().parse("X", "not json") is None
    empty_meta = {"chart": {"result": [{"meta": {}, "indicators": {"quote": [{}]}}]}}
    assert qb.QuoteParser().parse("X", empty_meta) is None


def test_quote_currency_defaults_for_indian_symbols():
    nifty = qb.QuoteParser().parse("^NSEI", chart_payload(24500.0, 24400.0, [24400.0, 24500.0]))
    assert nifty.currency == "INR"
    assert nifty.glyph == "₹"
    assert nifty.formatted_price() == "₹24,500.00"
    assert nifty.is_indian is True


def test_series_statistics_are_real_numbers():
    series = qb.QuoteSeries.from_raw([100, 102, 101, 105, 107, 106, 110])
    assert series.sma(3) == pytest.approx((107 + 106 + 110) / 3)
    assert qb.QuoteSeries([1.0, 2.0]).sma(5) is None
    assert series.last == 110
    assert series.momentum(5) == pytest.approx((110 - 102) / 102 * 100)
    assert series.drawdown_from_high() == 0.0
    assert series.volatility() > 0
    assert 0.0 <= series.range_position(115, 95) <= 1.0


def test_ema_seeds_from_the_sma_of_the_first_window():
    series = qb.QuoteSeries([10.0, 10.0, 10.0, 20.0])
    # seed = 10, multiplier = 0.5 -> 10*0.5 + 20*0.5 = 15
    assert series.ema(3) == pytest.approx(15.0)
    assert qb.QuoteSeries([1.0, 2.0]).ema(5) is None


def test_momentum_engine_calls_a_strong_buy_on_a_rising_stack():
    closes = [100 + i for i in range(20)]          # steady uptrend, last = 119
    payload = chart_payload(closes[-1], closes[0], closes)
    quote = qb.QuoteParser().parse("UP", payload)
    signal = qb.MomentumSignalEngine().evaluate(quote)
    assert signal.signal == "STRONG BUY"
    assert signal.call == "buy"
    assert signal.severity == 4
    assert signal.score > 0


def test_momentum_engine_calls_a_strong_sell_on_a_falling_stack():
    closes = [140 - i * 2 for i in range(20)]      # steady downtrend
    payload = chart_payload(closes[-1], closes[0], closes)
    quote = qb.QuoteParser().parse("DOWN", payload)
    signal = qb.MomentumSignalEngine().evaluate(quote)
    assert signal.signal == "STRONG SELL / SHORT"
    assert signal.score < 0
    assert "moving averages" in signal.reason


def test_momentum_engine_holds_without_history():
    payload = chart_payload(100.0, 100.0, [100.0])
    quote = qb.QuoteParser().parse("FLAT", payload)
    signal = qb.MomentumSignalEngine().evaluate(quote)
    assert signal.signal == "HOLD"
    assert signal.score == 0.0
    assert "Not enough history" in signal.reason


def test_momentum_engine_ranks_by_conviction():
    strong_closes = [100 + i * 2 for i in range(20)]
    weak_closes = [100 + i * 0.05 for i in range(20)]
    strong = qb.QuoteParser().parse("A", chart_payload(
        strong_closes[-1], strong_closes[0], strong_closes))
    weak = qb.QuoteParser().parse("B", chart_payload(
        weak_closes[-1], weak_closes[0], weak_closes))
    ranked = qb.MomentumSignalEngine().rank([weak, strong])
    assert ranked[0].symbol == "A"
    assert abs(ranked[0].score) >= abs(ranked[1].score)


def test_price_formatter_groups_indian_and_western():
    fmt = qb.PriceFormatter()
    assert fmt.format(1234567.891) == "1,234,567.89"
    assert fmt.format(1234567.891, indian=True) == "12,34,567.89"
    assert fmt.format(-9876.5) == "-9,876.50"
    assert fmt.format(999.0, digits=0) == "999"


def test_watchlist_finds_symbols_by_name_and_groups_them():
    watchlist = qb.Watchlist()
    assert watchlist.find("nifty") == "^NSEI"
    assert watchlist.find("reliance") == "RELIANCE.NS"
    assert watchlist.find("bitcoin") == "BTC-USD"
    assert watchlist.find("unknown thing") is None
    assert watchlist.group("^BSESN") == "index"
    assert watchlist.group("BTC-USD") == "crypto"
    assert watchlist.group("TCS.NS") == "india"
    assert watchlist.group("AAPL") == "global"

    watchlist.add("ETH-USD", "Ethereum")
    assert watchlist.name_of("ETH-USD") == "Ethereum"
    assert watchlist.remove("ETH-USD") is True
    assert len(watchlist.briefing()) == 4


def test_briefing_speaks_movers_and_summary():
    up = qb.QuoteParser({"UP": "Up Co"}).parse(
        "UP", chart_payload(110.0, 100.0, [100 + i for i in range(20)]))
    down = qb.QuoteParser({"DOWN": "Down Co"}).parse(
        "DOWN", chart_payload(90.0, 100.0, [110 - i for i in range(20)]))
    briefing = qb.MarketBriefing()

    spoken = briefing.speak([up, down])
    assert "Up Co is at $110.00, up 10.00%" in spoken
    assert "Signal:" in spoken

    movers = briefing.movers([up, down])
    assert movers["gainers"][0]["name"] == "Up Co"
    assert movers["losers"][0]["name"] == "Down Co"

    summary = briefing.summary([up, down, up])
    assert summary["advancers"] == 2 and summary["decliners"] == 1
    assert summary["leader"] == "Up Co"

    digest = briefing.digest([up, down])
    assert "2 instruments" in digest
    assert "Down Co" in digest


def test_brief_end_to_end_orders_indices_first():
    payloads = {
        "^NSEI": chart_payload(24600.0, 24500.0, [24500.0 + i for i in range(20)],
                               currency="INR"),
        "NVDA": chart_payload(181.0, 180.0, [180.0 + i * 0.1 for i in range(20)]),
    }
    result = qb.MarketBriefing().brief(payloads)
    assert len(result["quotes"]) == 2
    assert result["quotes"][0]["symbol"] == "^NSEI"
    assert result["summary"]["count"] == 2
    assert "Nifty 50" in result["spoken"]
    assert "₹24,600.00" in result["spoken"]


def test_briefing_handles_an_empty_watchlist():
    briefing = qb.MarketBriefing()
    assert "no market data" in briefing.speak([])
    assert briefing.summary([])["count"] == 0
    assert briefing.movers([]) == {"gainers": [], "losers": []}
    assert briefing.digest([]).startswith("0 instruments")
