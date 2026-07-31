#!/usr/bin/env python3
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nodes.archive_node import select_vector_query
from nodes.archive_node import get_context


def test_select_vector_query_uses_hyde_override():
    assert select_vector_query("what did I do in 2018?", "Intel Optane AEP mailbox automation script") == "Intel Optane AEP mailbox automation script"


def test_select_vector_query_falls_back_to_raw_when_hyde_short():
    assert select_vector_query("what did I do in 2018?", "short") == "what did I do in 2018?"


def test_select_vector_query_falls_back_to_raw_when_hyde_empty():
    assert select_vector_query("what did I do in 2018?", None) == "what did I do in 2018?"
    assert select_vector_query("what did I do in 2018?", "") == "what did I do in 2018?"
    assert select_vector_query("what did I do in 2018?", "   ") == "what did I do in 2018?"


def test_get_context_accepts_hyde_vector_text_param():
    assert "hyde_vector_text" in get_context.__code__.co_varnames


def test_no_regex_qpr_in_archive_retrieval():
    archive_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nodes", "archive_node.py")
    with open(archive_src, "r") as f:
        content = f.read()
    assert "qpr_refine_query" not in content


if __name__ == "__main__":
    test_select_vector_query_uses_hyde_override()
    test_select_vector_query_falls_back_to_raw_when_hyde_short()
    test_select_vector_query_falls_back_to_raw_when_hyde_empty()
    test_get_context_accepts_hyde_vector_text_param()
    test_no_regex_qpr_in_archive_retrieval()
    print("\n✅ QPR (AI-driven) & HyDE Refinement tests passed cleanly!")
