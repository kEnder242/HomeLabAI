import os
import json
import logging
import datetime
import asyncio
import re
from typing import List, Dict

from infra.atomic_io import atomic_write_json, atomic_write_text

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_briefs")
CONFIG_FILE = os.path.join(BASE_DIR, "../config/recruiter_config.json")
SIGNATURES_FILE = os.path.join(BASE_DIR, "../config/team_signatures.json")

def load_config():
    default = {
        "target_roles": ["Senior Platform Telemetry Engineer"],
        "target_companies": ["NVIDIA"],
        "keywords": ["telemetry"],
        "search_sites": ["hiring.cafe", "linkedin"]
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def load_signatures():
    if os.path.exists(SIGNATURES_FILE):
        try:
            with open(SIGNATURES_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [RECRUITER] %(message)s")
config = load_config()
signatures = load_signatures()

class NightlyRecruiter:
    def __init__(self, archive_client=None, brain_client=None, browser_client=None):
        self.archive = archive_client
        self.brain = brain_client
        self.browser = browser_client
        self.config = config
        self.signatures = signatures
        self.ledger_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/processed_jobs.json")

    async def calculate_semantic_match(self, jd_text: str) -> Dict:
        """
        [RE-FEAT-167.1] Multi-Vector Scoring Refactor.
        Tasks the Sovereign Brain with a semantic pass against Team Signatures.
        """
        if not self.brain or not jd_text:
            return {"score": 0.5, "bucket": "Unknown", "evidence": "No brain or text available."}

        prompt = f"""
        [ROLE] You are the Lead Engineer Auditor.
        [TASK] Evaluate the following Job Description (JD) against our Team Signature Buckets.
        
        [TEAM SIGNATURES]
        {json.dumps(self.signatures, indent=2)}
        
        [JOB DESCRIPTION]
        {jd_text[:5000]}
        
        [RULES]
        1. Identify the primary matching Team Signature Bucket.
        2. Calculate a Match Score (0.0 to 1.0).
        3. Provide 'Evidence of Alignment': Map requirements to our signatures.
        4. Format as JSON: {{"bucket": "...", "score": 0.85, "evidence": "..."}}
        """
        
        try:
            res = await self.brain.call_tool("deep_think", arguments={"task": prompt})
            # Use regex to extract JSON
            match = re.search(r'(\{.*?\})', res.content[0].text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception as e:
            logging.error(f"[RECRUITER] Semantic scoring failed: {e}")
            
        return {"score": 0.5, "bucket": "General", "evidence": "Failed to perform semantic audit."}

    def is_duplicate(self, job: Dict) -> bool:
        """Checks the persistent ledger to prevent redundant alerts."""
        if not os.path.exists(self.ledger_path):
            return False
        try:
            with open(self.ledger_path, "r") as f:
                ledger = json.load(f)
            
            # Case 1: Direct URL match
            if job.get("url") and job.get("url") in ledger:
                return True
                
            # Case 2: Fuzzy Identity match (Title + Company)
            identity = (job.get("title", "") + job.get("company", "")).lower().replace(" ", "").strip()
            if not identity: return False
            
            for item in ledger:
                if not item.startswith("http") and identity == item.lower().replace(" ", "").strip():
                    return True
            
            return False
        except Exception:
            return False

    def mark_as_processed(self, job: Dict):
        """Logs the job into the ledger."""
        try:
            if not os.path.exists(self.ledger_path):
                ledger = []
            else:
                with open(self.ledger_path, "r") as f:
                    ledger = json.load(f)
            
            url = job.get("url")
            identity = (job.get("title", "") + job.get("company", ""))
            
            if url and url not in ledger:
                ledger.append(url)
            if identity and identity not in ledger:
                ledger.append(identity)
                
            atomic_write_json(self.ledger_path, ledger[-1000:])
        except Exception as e:
            logging.error(f"[RECRUITER] Ledger Update Failed: {e}")

    async def fetch_career_context(self):
        """Retrieves high-level summary from the Archive Node."""
        if not self.archive:
            return "Expert in Silicon Validation and Telemetry."
        try:
            res_json = await self.archive.call_tool("get_context", arguments={"query": "Diamond Rank technical gems", "n_results": 5})
            res = json.loads(res_json.content[0].text)
            return res.get("text", "Expert in Silicon Validation.")
        except Exception:
            return "Expert in Silicon Validation."

    async def search_for_jobs(self) -> List[Dict]:
        """Uses the Brain's reasoning to identify target listings."""
        if not self.brain:
            return []
        
        query = f"Target Roles: {', '.join(self.config.get('target_roles', []))}. Keywords: {', '.join(self.config.get('keywords', []))}."
        task = f"Find 3-5 high-fidelity job URLs matching these criteria: {query}. Provide ONLY a list of URLs."
        
        try:
            res = await self.brain.call_tool("deep_think", arguments={"task": task})
            urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', res.content[0].text)
            
            unique_urls = []
            for u in urls:
                clean_u = u.split("?")[0].rstrip("/")
                if clean_u not in [x.split("?")[0].rstrip("/") for x in unique_urls]:
                    unique_urls.append(u)
            
            jobs = []
            for url in unique_urls[:5]:
                jobs.append({"title": "Automated Search Result", "company": "External Site", "url": url, "description": ""})
            
            return jobs
        except Exception:
            return []

    async def verify_and_score_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """[RE-FEAT-168.2] JD Verification via Browser Node and Semantic Scoring."""
        scored_jobs = []
        for job in jobs:
            if self.is_duplicate(job):
                continue
                
            logging.info(f"[RECRUITER] Verifying: {job['url']}")
            jd_text = ""
            if self.browser:
                try:
                    res = await self.browser.call_tool("browse_url", arguments={"url": job['url']})
                    jd_text = res.content[0].text
                    if "Error:" in jd_text:
                        logging.warning(f"[RECRUITER] Verification failed for {job['url']}")
                        continue
                except Exception as e:
                    logging.error(f"[RECRUITER] Browser tool failed: {e}")
                    continue
            else:
                # Without browser, we can't verify, so we skip to maintain high-fidelity
                continue

            # Semantic Scoring
            audit = await self.calculate_semantic_match(jd_text)
            job.update(audit)
            job["jd_summary"] = jd_text[:500] + "..."
            scored_jobs.append(job)
            self.mark_as_processed(job)
            
        return scored_jobs

    async def generate_brief(self, jobs: List[Dict], context: str) -> (str, int):
        """[UI-042] Bucket-Aware Job Brief. Groups jobs by Team Signature Bucket."""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"job_brief_{date_str}.md"
        path = os.path.join(DRAFTS_DIR, filename)
        
        content = f"# 🕵️ Nightly Recruiter Brief: {date_str}\n\n"
        
        # Grouping
        buckets = {}
        for job in jobs:
            b = job.get("bucket", "General")
            if b not in buckets: buckets[b] = []
            buckets[b].append(job)
            
        valid_jobs = len(jobs)
        if valid_jobs == 0:
            content += "_No new high-fidelity verified matches found since last scan._\n"
        else:
            for b_name, b_jobs in buckets.items():
                content += f"### 📦 Bucket: {b_name}\n"
                for job in b_jobs:
                    content += f"*   **{job['title']}** @ {job['company']}\n"
                    content += f"    *   [Apply Here]({job['url']})\n"
                    content += f"    *   **Match Score:** {job.get('score', 0.5)}\n"
                    content += f"    *   **Evidence:** {job.get('evidence', 'N/A')}\n\n"

        content += "\n## 🔗 Strategic Search Manifest\n"
        for site in self.config.get("search_sites", []):
            if "hiring.cafe" in site:
                content += "* [Hiring.Cafe: Silicon Forest Telemetry](https://hiring.cafe/search?q=telemetry+silicon+validation+hillsboro)\n"
            elif "linkedin" in site:
                content += "* [LinkedIn: High-Fidelity Validation](https://www.linkedin.com/jobs/search/?keywords=telemetry%20silicon%20validation)\n"
        
        content += "\n\n---\n*Generated by HomeLabAI (The Nightly Recruiter)*"
        
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        atomic_write_text(path, content)
        
        return path, valid_jobs

async def run_recruiter_task(archive_interface=None, brain_interface=None, browser_interface=None):
    recruiter = NightlyRecruiter(archive_interface, brain_interface, browser_interface)
    logging.info("Waking up for Nightly Multi-Vector Acquisition drive...")
    
    ctx = await recruiter.fetch_career_context()
    raw_jobs = await recruiter.search_for_jobs()
    
    # [PHASE 2] Verification and Scoring
    verified_jobs = await recruiter.verify_and_score_jobs(raw_jobs)
    
    brief_path, new_count = await recruiter.generate_brief(verified_jobs, ctx)
    
    # [UI-043] Dashboard Reporting
    try:
        report_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_report.json")
        
        # Calculate density
        density = {}
        for job in verified_jobs:
            b = job.get("bucket", "General")
            density[b] = density.get(b, 0) + 1
            
        report = {
            "last_run": datetime.datetime.now().isoformat(),
            "status": "UPLINK_NOMINAL",
            "brief_path": os.path.basename(brief_path),
            "new_jobs": new_count,
            "bucket_density": density
        }
        atomic_write_json(report_path, report)
    except Exception:
        pass
    
    return brief_path

if __name__ == "__main__":
    # Note: Requires interfaces to be passed in for full functionality
    asyncio.run(run_recruiter_task())
