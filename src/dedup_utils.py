def get_new_text(old_text, new_window_text, lookback=10):
    if not old_text: return new_window_text

    old_words = old_text.strip().lower().split()
    new_words = new_window_text.strip().lower().split()
    if not new_words: return ""

    # 1. Full Phrase Repetition (The "Echo" check)
    # If the entire new window is already at the end of our transcript, ignore it.
    window_len = len(new_words)
    if old_words[-window_len:] == new_words:
        return ""

    # 1.5. Sub-phrase duplication (Improved Echo check)
    # If the new window is short and contained anywhere in the recent history, ignore.
    if window_len <= 3:
        recent_history = " ".join(old_words[-lookback:])
        if " ".join(new_words) in recent_history:
            return ""

    # 2. Sliding Window Overlap (The "Stitch" check)
    # Increase max overlap significantly to handle longer phrases
    max_overlap = min(len(old_words), len(new_words))

    for i in range(max_overlap, 0, -1):
        if old_words[-i:] == new_words[:i]:
            # Return the original casing from the new text
            new_original_words = new_window_text.strip().split()
            return " ".join(new_original_words[i:])

    return new_window_text
