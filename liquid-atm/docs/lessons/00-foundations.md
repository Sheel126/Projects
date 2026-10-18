# Lesson 00: Foundations

Read this before the Phase 0 code. Each section answers a *why* that the code depends on.

---

## 1. The shape of the system: intents flow one way, and the broker is the truth

```
             research side (Python)                    money side (Java)
 ┌──────────────────────────────────────────┐    ┌──────────────────────────────────┐
 │ data → universe → regime → screener →    │    │ risk gate → tax/blacklist gate → │
 │ LLM veto → TRADE INTENTS (rows in PG)    │ ─▶ │ Alpaca OMS → fills → tax ledger  │
 └──────────────────────────────────────────┘    └──────────────────────────────────┘
                                                              ▲         │
                                                              └─ reconcile ◀─ Alpaca (source of truth)
```

- **Python never places orders.** It produces *intents*: "I would like to buy X at a limit of L, with TP T and SL S, because of R." An intent is a proposal, not an action. That gives us one small, auditable place where money moves, and a hard line between "research code I change every day" and "execution code I change rarely".
- **Java is allowed to say no.** It applies every gate that protects capital: exposure caps, the wash-sale blacklist, kill switches and the asset-class whitelist. If the Python service is down or returns garbage, the fallback is **"no new trades today"**. A bot that fails safe does nothing; a bot that fails unsafe does something random with real money.
- **The broker is the source of truth for positions.** Our database is a *cache* of what we believe happened. Networks drop replies, processes crash in the middle of an order, and Alpaca can fill partially. So the orchestrator always **reconciles**: it asks Alpaca what really exists and repairs local state to match. The `client_order_id` column is unique for this reason. If we crash after sending an order but before recording it, the retry reuses the same ID and Alpaca rejects the duplicate. That property is called *idempotency*.

## 2. Survivorship bias: the biggest trap with free data

Suppose you backtest a momentum strategy on **today's** Russell 1000 members over 2010–2025. Every company in that list *survived* to 2025 and grew large enough to be in the index. Companies that went bankrupt, were delisted or shrank out of the index are invisible. Momentum strategies buy stocks that are rising, and some rising stocks later crash to zero. Your backtest can't buy those, because they aren't in its universe. The result looks better than reality, often by **several percent a year**.

The fix has two parts:
1. **Point-in-time universe:** on each backtest date, only trade what was *in the index on that date* (Phase 1 builds `universe_membership` with an `as_of_date`).
2. **Delisted prices:** you need price history for the companies that disappeared. Free sources are patchy here, so in Phase 1 we **measure coverage** (the share of past members we have prices for) and in Phase 4 we **haircut** backtest returns in proportion. The data can't be made perfect, but the result can be made *honest*.

## 3. T+1 settlement, margin vs. cash, and PDT

- **T+1:** US equity trades settle one business day after the trade. In a **cash account**, the proceeds of a sale can't be used to buy until they settle. Buying with unsettled money and then selling that position before settlement is a *good-faith violation*, and repeated violations get the account restricted. That is the "cash drag" your spec worries about.
- **Margin account with leverage capped at 1.0×:** the broker lends against unsettled proceeds, so settlement stops blocking you. We **never borrow**: the orchestrator caps exposure at 1.0× equity in software. You get the plumbing benefit of margin without the risk.
- **PDT:** the old rule (4 or more day trades in 5 days with under $25k equity leads to a restriction) was repealed. The SEC approved the change in April 2026 and FINRA made it effective June 4, 2026. **Brokers have until October 2027 to implement it**, so the Phase 0 probe records exactly what Alpaca's account flags report today. This matters because a bracket stop can trigger the same day as the entry, and that counts as a day trade.
- The conclusion: daily **tranches** are still useful, but as *risk pacing* (spreading entries across days so one bad day doesn't fill the whole book), not as a settlement workaround.

## 4. Rate limiting: why a sliding window, and why it must be atomic

Free APIs punish you for going too fast: Alpaca allows 200 requests/min, SEC EDGAR allows 10 requests/sec (and bans your IP if you exceed it), and yfinance throttles without saying so.

**A fixed window** ("reset the counter at the top of each minute") has a boundary bug. You can send 200 requests at 12:00:59 and another 200 at 12:01:00, which is 400 in two seconds.

**A sliding window** answers "how many requests in the *last* 60 seconds?" at every moment. We store each request's timestamp in a Redis **sorted set** (ZSET), where the score is the timestamp:

```
ZREMRANGEBYSCORE key 0 (now - window)   -- 1. forget requests older than the window
ZCARD key                               -- 2. count what's left
if count < limit: ZADD key now member   -- 3. admit, record this request
PEXPIRE key window                      -- 4. let idle keys clean themselves up
```

**Why Lua?** Suppose two workers run steps 1–3 as separate commands. Both could read `count = 199` and both add a request, which makes 201 and breaks the limit. That is a *race condition*. Redis runs a Lua script **atomically**: no other command runs in the middle of it. So "check and add" becomes one indivisible operation. This is the same idea as a database transaction or a CPU compare-and-swap.

The same tool gives us a **GPU semaphore**: at most N concurrent Ollama calls. Local inference has no rate limit in dollars, but it has a *memory* limit. Two 14B-parameter requests at once can exceed 16 GB of VRAM, spill into system RAM and become 10× slower.

## 5. Why the LLM cache is exact, never semantic

A **semantic cache** embeds the prompt as a vector and returns a stored answer if a "similar enough" prompt was seen before. That's fine for chatbots, and **dangerous for trading**. For example:

- "NVDA 8-K: Q2 revenue beat, guidance raised"
- "NVDA 8-K: Q2 revenue beat, guidance cut"

These two filings are over 95% similar as vectors and mean opposite things. A veto gate that reuses the first verdict for the second filing is worse than having no gate.

So the cache key is a **SHA-256 hash of exactly**: the model tag, the prompt version, the output schema, and the canonical input (ticker plus the IDs of the filings and news used). Change any of them, and the cache misses. That includes switching from `qwen2.5:14b` to `qwen3:14b`, or editing the prompt, so we can never silently reuse a verdict from a different "brain". pgvector still has a role in Phase 5, for *retrieving related context* (finding past filings about the same company), but not for *reusing decisions*.

## 6. Structured output: making a language model behave like a function

We need `{"catalyst_type": "earnings_beat", "quality": 0.8, ...}`, not a paragraph. Ollama's `/api/chat` accepts a `format` field containing a **JSON Schema**. It constrains token sampling so that the model *can only* produce text that parses into that schema. We still **validate** with pydantic on our side (checking ranges, enums and required fields), because enforcing the format isn't the same as the content being correct. On a validation failure we retry once, and after that we **fail closed**: the candidate is rejected.

`temperature = 0` makes answers repeatable, which matters for reproducing a decision later.

## 7. The cost model of local inference

With paid APIs, cost scales with tokens. Locally, cost is **time plus electricity**, and the real constraint is **throughput**:

- 10 candidates a day × about 2,000 input tokens each, at maybe 20–40 tokens/sec generation on a 16 GB card, adds up to minutes a day. That's fine.
- Screening 1,000 stocks with the LLM would take hours, and is the reason the LLM comes **last** in the funnel. Cheap math filters 1,000 names down to about 10, and only then does the expensive "intuition" run.
- `llm_smoke.py` measures your real tokens/sec, which becomes our throughput budget.

## 8. What Phase 0 builds, and why each piece exists

| Piece | Why |
|---|---|
| `docker-compose.yml` with health checks | Services start in dependency order and nothing talks to a database that isn't ready |
| `V1__baseline.sql` (Flyway, owned by Java) | One owner for the schema; migrations are versioned and repeatable |
| Redis Lua sliding window | Protects the free APIs; covered in §4 |
| GPU semaphore | Protects VRAM; covered in §4 |
| LLM gateway (Ollama, exact cache, schema, validation) | Covered in §5–6 |
| `alpaca_probe.py` | We verify how the broker *actually* behaves (brackets, PDT flags, data feeds) instead of trusting documentation |
