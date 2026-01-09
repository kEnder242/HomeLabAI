def get_new_text(old_text, new_window_text):
    if not old_text: return new_window_text
    old_words = old_text.strip().lower().split()
    new_words = new_window_text.strip().lower().split()
    if not new_words: return ""
    
    # Increase max overlap significantly to handle longer phrases
    # And we'll use a larger slice if possible
    max_overlap = min(len(old_words), len(new_words))
    
    for i in range(max_overlap, 0, -1):
        if old_words[-i:] == new_words[:i]:
            # Return the original casing from the new text
            new_original_words = new_window_text.strip().split()
            return " ".join(new_original_words[i:])
            
    return new_window_text
