from dedup_utils import get_new_text

def test_deduplication():
    print("Running Deduplication Tests...")
    
    # Case 1: Simple overlap
    t1 = "Hello my name is"
    t2 = "my name is Jason"
    res1 = get_new_text(t1, t2)
    print(f"Test 1: '{t1}' + '{t2}' -> '{res1}' (Expected: 'Jason')")
    assert res1.lower() == "jason"

    # Case 2: No overlap
    t1 = "Hello"
    t2 = "World"
    res2 = get_new_text(t1, t2)
    print(f"Test 2: '{t1}' + '{t2}' -> '{res2}' (Expected: 'World')")
    assert res2.lower() == "world"

    # Case 3: Phrase duplication (The reported bug)
    # User said: "Is the Brain. The Brain sleeping."
    t1 = "Is the Brain"
    t2 = "the Brain sleeping"
    res3 = get_new_text(t1, t2)
    print(f"Test 3: '{t1}' + '{t2}' -> '{res3}' (Expected: 'sleeping')")
    assert res3.lower() == "sleeping"
    
    # Case 4: Long phrase (Greater than 5 words)
    t1 = "I am sitting in the office coding"
    t2 = "sitting in the office coding a new feature"
    res4 = get_new_text(t1, t2)
    print(f"Test 4: '{t1}' + '{t2}' -> '{res4}' (Expected: 'a new feature')")
    assert res4.lower() == "a new feature"

    # Case 5: Casing differences
    t1 = "IS THE BRAIN"
    t2 = "is the brain sleeping"
    res5 = get_new_text(t1, t2)
    print(f"Test 5: '{t1}' + '{t2}' -> '{res5}' (Expected: 'sleeping')")
    assert res5.lower() == "sleeping"

    # Case 6: Full Phrase Repetition (The Pause Echo)
    t1 = "Who is in here? In here"
    t2 = "In here"
    res6 = get_new_text(t1, t2)
    print(f"Test 6: '{t1}' + '{t2}' -> '{res6}' (Expected: '')")
    assert res6 == ""

    print("✅ All tests passed!")

if __name__ == "__main__":
    test_deduplication()