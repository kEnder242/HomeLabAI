import sys
import os
import numpy as np

# Mocking some things to avoid full MCP/ChromaDB init for logic test if possible,
# but we need the EF and Vectors.
# Let's just import the necessary bits.

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.nodes.archive_node import ef, brain_vectors, pinky_vectors, cosine_similarity

def test_classify(query):
    query_vector = np.array(ef([query])[0])

    brain_sim = max([cosine_similarity(query_vector, bv) for bv in brain_vectors])
    pinky_sim = max([cosine_similarity(query_vector, pv) for pv in pinky_vectors])

    threshold = 0.4
    target = "PINKY"
    if brain_sim > pinky_sim and brain_sim > threshold:
        target = "BRAIN"
    elif brain_sim > 0.6:
        target = "BRAIN"

    print(f"Query: '{query}'")
    print(f"  Target: {target}")
    print(f"  Brain Sim: {brain_sim:.4f}")
    print(f"  Pinky Sim: {pinky_sim:.4f}")
    print("-" * 20)

queries = [
    "What is the capital of France?",
    "Tell me a joke!",
    "Calculate the square root of 144",
    "Hey Pinky, how's it going?",
    "Write a python script to scrape a website",
    "Narf!",
    "Who won the world cup in 2022?",
    "What do you think of the weather?",
    "Wake up the Brain",
    "Explain quantum entanglement"
]

if __name__ == "__main__":
    for q in queries:
        test_classify(q)
