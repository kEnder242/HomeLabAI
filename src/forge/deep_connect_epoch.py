import os
import json
import logging
import glob

# Paths
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
KNOWLEDGE_BASE = os.path.expanduser("~/Dev_Lab/knowledge_base")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "expertise/bkm_master_manifest.jsonl")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [DEEP-CONNECT] %(message)s')

# Year to Raw Log Mapping
LOG_MAP = {
    "2005": "notes_2005.txt",
    "2006": "notes_2006_EPSD.txt",
    "2011": "notes_2015_DSD.txt",
    "2012": "notes_2015_DSD.txt",
    "2013": "notes_2015_DSD.txt",
    "2014": "notes_2015_DSD.txt",
    "2015": "notes_2015_DSD.txt",
    "2016": "notes_2016_MVE.txt",
    "2017": "notes_2018_PAE.txt",
    "2018": "notes_2018_PAE.txt",
    "2019": "notes_2018_PAE.txt",
    "2020": "notes_2024_PIAV.txt",
    "2021": "notes_2024_PIAV.txt",
    "2022": "notes_2024_PIAV.txt",
    "2023": "notes_2024_PIAV.txt",
    "2024": "notes_2024_PIAV.txt",
}

def extract_context(log_path, snippet, window=10):
    """Searches for snippet in log_path and returns surrounding lines."""
    if not os.path.exists(log_path):
        return None
    
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Clean snippet for search - try whole then parts
        sub_snippets = [s.strip() for s in snippet.split(",") if len(s.strip()) > 5]
        if not sub_snippets:
            sub_snippets = [snippet.strip()]

        for clean_snippet in sub_snippets:
            clean_snippet = clean_snippet.lower()
            if len(clean_snippet) < 5:
                continue
            
            for i, line in enumerate(lines):
                if clean_snippet in line.lower():
                    start = max(0, i - window)
                    end = min(len(lines), i + window + 1)
                    return "".join(lines[start:end]).strip()
    except Exception as e:
        logging.error(f"Error reading {log_path}: {e}")
    return None

def run_epoch():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    dataset = []
    
    json_files = glob.glob(os.path.join(DATA_DIR, "20*.json"))
    logging.info(f"Scanning {len(json_files)} artifacts...")

    for jf in json_files:
        year = os.path.basename(jf).replace(".json", "")
        log_file = LOG_MAP.get(year)
        if not log_file:
            continue
        
        log_path = os.path.join(KNOWLEDGE_BASE, log_file)
        
        try:
            with open(jf, 'r') as f:
                data = json.load(f)
            
            for item in data:
                if item.get('rank', 0) >= 4:
                    evidence = item.get('evidence', '')
                    summary = item.get('summary', '')
                    
                    # Try finding the evidence context
                    context = None
                    if summary: # Primary search key is now summary
                        logging.info(f"Searching for summary: {summary[:50]}... in {log_path}")
                        context = extract_context(log_path, summary)
                    
                    if not context and summary:
                        # Fallback: search for keywords from summary
                        keywords = summary.split()[:5]
                        if len(keywords) >= 3:
                            context = extract_context(log_path, " ".join(keywords))
                    
                    if context:
                        # Forged Instruction-Response Pair
                        pair = {
                            "instruction": f"Extract technical evidence and architectural BKM for the following scenario: {summary}",
                            "input": "",
                            "output": f"### TACTICAL EVIDENCE (18-YEAR ARCHIVE):\\n{context}\\n\\n### ARCHITECTURAL BKM:\\nOne-liner: {summary}\\nCore Logic: {evidence}"
                        }
                        dataset.append(pair)
                        
        except Exception as e:
            logging.error(f"Error processing {jf}: {e}")

    with open(OUTPUT_FILE, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    logging.info(f"Epoch Complete. Generated {len(dataset)} high-fidelity BKM pairs in {OUTPUT_FILE}")

if __name__ == "__main__":
    run_epoch()
