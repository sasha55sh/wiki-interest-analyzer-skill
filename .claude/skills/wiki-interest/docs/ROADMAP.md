# Development Roadmap

How to extend the wiki-interest skill for more complex research and larger datasets.

## Phase 1: Bigger Data Volumes (4–6 weeks)

**Goal:** Analyze hundreds of articles and dozens of languages simultaneously.

### Bulk downloads instead of API

- **Current:** Per-article REST API (~1 req per article, rate-limited)
- **Future:** Wikimedia dumps + DuckDB or Parquet for batch loading
  - `pageviews-` dumps: https://dumps.wikimedia.org/
  - Load 10 years of monthly data for 100 topics in minutes, not hours

### Batch mode

```bash
wiki-interest run --batch topics.csv --langs uk,pl,cs,sk,de
```

Where `topics.csv`:
```
topic,qids
Astronomy,Q333
Machine learning,Q11019
```

### Implementation

- Add `scripts/wiki_interest/batch.py` for parallel processing
- Use `concurrent.futures.ThreadPoolExecutor` (10–20 workers)
- Cache per-language aggregates to avoid re-fetching

### Tests

- ✓ Benchmark: 100 topics × 10 languages in < 2 minutes
- ✓ Consistency: dump-based results match API-based results for overlap periods

---

## Phase 2: Smarter Topic Selection (4–6 weeks)

**Goal:** Automatically expand a topic to related articles; find unexpected interest patterns.

### Auto-expand via Wikidata

- Topic "Machine learning" → Also include: "Deep learning", "Neural network", "AI", "Artificial intelligence"
- Use Wikidata's `subclass of` and `part of` relations
- Aggregate views across the basket

### Implementation

```python

def expand_topic(qid: str) -> list[str]:
    """Get related QIDs from Wikidata."""
```

### Clickstream data

- Not just pageviews, but *where readers come from*
- Wikimedia Clickstream: which articles link to the topic
- Signal: "machine learning" interest from CS educators, researchers, students

### Tests

- ✓ Expansion doesn't change results for single-article topics
- ✓ Basket aggregation is correct (sum of articles)
- ✓ Clickstream data integrates without errors

---

## Phase 3: Advanced Analytics (6–8 weeks)

**Goal:** Deeper insights: seasonality, breakpoints, forecasts.

### Seasonality decomposition

- Current: Detect high seasonality as a caveat
- Future: Use STL decomposition to separate trend from seasonal patterns
  - Show "cleaned" trend (seasonal component removed)
  - Plot seasonal pattern separately

### Breakpoint detection

- When did interest fundamentally shift?
- Use `ruptures` library to find change points
- Report: "Interest in X surged on [date]" with confidence

### Forecasting

- Simple: next 6 months, with prediction intervals
- Model: ARIMA or exponential smoothing
- Include uncertainty bands

### Comparative baselines

- "Interest in X grew 20% YoY; compare to related topic Y: [growth]%"
- Helps user understand if 20% is big or small

### Tests

- ✓ Synthetic data with known seasonality: decomposition recovers it
- ✓ Synthetic breakpoint at month 12: detected with p < 0.05
- ✓ Forecast accuracy on holdout test set: MAPE < 20%

---

## Phase 4: Process & Quality (2–4 weeks)

**Goal:** Every feature comes with evals and documentation.

### Evaluation framework

- Each new feature gets 3–5 eval cases in `evals/cases.yaml`
- Regression tests on cheap models (Qwen, Llama)
- CI/CD: run evals on every commit

### Methodology versioning

- `analysis.json` includes `methodology_version: "0.1.0"`
- If formula changes, increment version
- Old reports remain reproducible

### Session context preservation

- Already in `runs/<id>/spec.json`
- User can refine queries without starting over
- "Add Polish" doesn't re-fetch Ukrainian data

### Documentation

- Update `references/methodology.md` for each new metric
- Update `references/interpretation.md` for how to talk about it
- Sync `SKILL.md` with new commands

---

## Implementation Strategy

### For each phase:

1. **Add eval cases first** — define success criteria
2. **Implement & test** — code to pass evals
3. **Refine based on failures** — iterate quickly
4. **Document** — methods, caveats, examples
5. **Merge to main** — never without passing evals

### Cheap model testing

Each phase should pass eval suite on:
- ✓ Qwen 7B (free)
- ✓ Llama 2 7B (free)

If model struggles, the CLI/SKILL.md is too complex; simplify.

### Timelines

- **Phase 1** (Bulk data): 4–6 weeks, 1 developer
- **Phase 2** (Smart topics): 4–6 weeks, 1 developer  
- **Phase 3** (Advanced analytics): 6–8 weeks, 1–2 developers
- **Phase 4** (Process): Ongoing, part of every merge

**Total: 4–5 months to production-grade skill**

---

## Current State (v0.1.0)

✓ Single topic, multiple languages, basic trends  
✓ Confidence scoring & caveats  
✓ PDF reports  
✓ Local evals passing  
✓ AI-generated code verified  

**Next:** Phase 1 (bulk data) or Phase 2 (smart topics) based on user demand.
