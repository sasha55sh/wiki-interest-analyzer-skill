#!/usr/bin/env python
"""Run eval cases on OpenRouter (Qwen, Llama, etc.) or Claude API."""

import os
import sys

import httpx

EVALS = [
    {
        "name": "astronomy_uk_basic",
        "prompt": "Analyze Wikipedia pageview trend: How has interest in astronomy changed in Ukrainian Wikipedia over the last 24 months?",
        "skill_command": 'wiki-interest run "Astronomy" --langs uk --months 24',
        "expect_in_response": ["run_id", "confidence", "uk"],
    },
    {
        "name": "intermittent_fasting_missing_lang",
        "prompt": "Check if intermittent fasting interest is growing in Polish and Czech Wikipedia.",
        "skill_command": 'wiki-interest run "Intermittent fasting" --langs pl,cs --months 24',
        "expect_in_response": ["pl", "missing", "cs"],
    },
    {
        "name": "ambiguous_resolve",
        "prompt": "Search for Mercury in Wikipedia. What ambiguity do you find?",
        "skill_command": 'wiki-interest resolve "Mercury" --langs uk,en',
        "expect_in_response": ["ambiguous_topic", "candidates"],
    },
]


def run_eval_openrouter(model: str = "qwen/qwen-2.5-7b-instruct-free"):
    """Run evals using OpenRouter API."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY env var not set")
        return 1

    client = httpx.Client(headers={"Authorization": f"Bearer {api_key}"})
    base_url = "https://openrouter.ai/api/v1"

    passed = 0
    total = len(EVALS)

    for eval_case in EVALS:
        print(f"\n[{eval_case['name']}]")
        print(f"  Command: {eval_case['skill_command']}")

        prompt = f"""You are a data analyst using the wiki-interest skill.
User: {eval_case['prompt']}

Please run the following command and summarize the results:
{eval_case['skill_command']}

Then explain what you found."""

        try:
            response = client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            result = response.json()
            answer = result["choices"][0]["message"]["content"]

            found_all = all(expect in answer for expect in eval_case["expect_in_response"])
            if found_all:
                print("  [PASS] All expected terms found")
                passed += 1
            else:
                missing = [e for e in eval_case["expect_in_response"] if e not in answer]
                print(f"  [FAIL] Missing: {missing}")

        except Exception as e:
            print(f"  [ERROR] {e}")

    print(f"\n[RESULT] {passed}/{total} evals passed on {model}")
    return 0 if passed == total else 1


def run_eval_local():
    """Run evals locally with mock API."""
    print("=== Local Evals (Offline) ===\n")
    from wiki_interest.cache import Cache
    from wiki_interest.fetch import Client
    from wiki_interest.resolve import TopicError, resolve

    passed = 0

    client, cache = Client(), Cache()
    try:
        resolve(client, cache, ["uk"], topic="Mercury")
        print("[FAIL] Should raise TopicError for Mercury")
    except TopicError as e:
        if e.code == "ambiguous_topic":
            print("[PASS] Ambiguous topic detected")
            passed += 1

    try:
        resolve(client, cache, ["uk"], topic="xyz_nonexistent_12345")
        print("[FAIL] Should raise TopicError for unknown topic")
    except TopicError as e:
        if e.code == "unknown_topic":
            print("[PASS] Unknown topic detected")
            passed += 1

    print(f"\n[RESULT] {passed}/2 local evals passed")
    return 0 if passed == 2 else 1


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--openrouter":
        model = sys.argv[2] if len(sys.argv) > 2 else "qwen/qwen-2.5-7b-instruct-free"
        return run_eval_openrouter(model)
    else:
        return run_eval_local()


if __name__ == "__main__":
    sys.exit(main())
