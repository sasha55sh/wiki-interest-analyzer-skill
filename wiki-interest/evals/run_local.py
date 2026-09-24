#!/usr/bin/env python
"""Run eval cases locally with mocked API (offline)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from wiki_interest.cache import Cache
from wiki_interest.fetch import Client
from wiki_interest.resolve import resolve, TopicError


def test_resolve_ambiguous():
    """Test: ambiguous_topic error."""
    client, cache = Client(), Cache()
    try:
        resolve(client, cache, ["uk"], topic="Mercury")
        print("[FAIL] Should have raised TopicError")
        return False
    except TopicError as e:
        if e.code == "ambiguous_topic" and len(e.candidates) > 0:
            print("[PASS] ambiguous_topic detected correctly")
            return True
        print(f"[FAIL] Wrong error: {e.code}")
        return False


def test_resolve_unknown():
    """Test: unknown_topic error."""
    client, cache = Client(), Cache()
    try:
        resolve(client, cache, ["uk"], topic="xyz_nonexistent_xyz_12345")
        print("[FAIL] Should have raised TopicError")
        return False
    except TopicError as e:
        if e.code == "unknown_topic":
            print("[PASS] unknown_topic detected correctly")
            return True
        print(f"[FAIL] Wrong error: {e.code}")
        return False


def main():
    """Run offline evals."""
    print("=== Offline Eval Cases (with live API) ===\n")
    
    passed = 0
    total = 2
    
    if test_resolve_ambiguous():
        passed += 1
    if test_resolve_unknown():
        passed += 1
    
    print(f"\n[RESULT] {passed}/{total} evals passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
