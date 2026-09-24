# Eval Guide: Running Tests on Cheap Models

## Prerequisites

```bash
export OPENROUTER_API_KEY=sk-or-...  # Get from https://openrouter.ai/keys
cd wiki-interest
uv sync
```

## Run Local Tests (No API Key Needed)

```bash
# Unit tests: 17 tests, all offline, ~5 seconds
uv run pytest tests/ -v

# Local eval: 2 core scenarios
uv run python evals/run_openrouter.py
```

Expected output:
```
=== Local Evals (Offline) ===

[PASS] Ambiguous topic detected
[PASS] Unknown topic detected

[RESULT] 2/2 local evals passed
```

## Run Full Eval on OpenRouter (Requires API Key)

### Option 1: Qwen (Free tier)

```bash
uv run python evals/run_openrouter.py --openrouter qwen/qwen-2.5-7b-instruct-free
```

Expected: Model will:
- Understand the skill (wiki-interest commands)
- Run commands correctly
- Summarize results with confidence and caveats

### Option 2: Llama (Free tier)

```bash
uv run python evals/run_openrouter.py --openrouter meta-llama/llama-2-7b-chat-free
```

### Option 3: Your Choice

OpenRouter free models list: https://openrouter.ai/docs/models

Pass any model: `--openrouter provider/model-name`

## Eval Scenarios

The script tests 3 core scenarios:

1. **astronomy_uk_basic**: Single-language trend analysis
   - Command: `run "Astronomy" --langs uk --months 24`
   - Expect: run_id, confidence, "uk"

2. **intermittent_fasting_missing_lang**: Missing language handling
   - Command: `run "Intermittent fasting" --langs pl,cs --months 24`
   - Expect: "pl" in langs_missing (no article), "cs" has data

3. **ambiguous_resolve**: Topic ambiguity detection
   - Command: `resolve "Mercury" --langs uk,en`
   - Expect: ambiguous_topic error, multiple candidates shown

## Interpreting Results

**[PASS]**: Model correctly ran the command and found expected keywords in its response.

**[FAIL]**: Model ran the command but missed expected keywords or made incorrect interpretation.

**[ERROR]**: API call failed or timeout.

## Adding More Eval Cases

Edit `evals/run_openrouter.py` and add to the `EVALS` list:

```python
{
    "name": "your_test_case",
    "prompt": "User's question here",
    "skill_command": 'wiki-interest run "Topic" --langs uk',
    "expect_in_response": ["keyword1", "keyword2"],
}
```

Then re-run the full eval.

## Success Criteria

✓ All 3 scenarios pass on at least one free model (Qwen or Llama)  
✓ No API errors or timeouts  
✓ Model demonstrates understanding of:
  - When to use which command
  - How to interpret confidence & caveats
  - How to handle missing data

## Troubleshooting

**"OPENROUTER_API_KEY env var not set"**
```bash
export OPENROUTER_API_KEY=sk-or-your-key
```

**Timeout on free model**
- Free models can be slow; increase timeout in code if needed
- Try a different model with faster inference

**Model hallucinates numbers**
- Expected; eval checks for structure, not exact values
- Real agent would use JSON output, not model's invented numbers
