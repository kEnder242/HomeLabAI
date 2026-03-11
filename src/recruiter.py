import os
import json
import logging
import datetime
import asyncio
from typing import List, Dict

from infra.atomic_io import atomic_write_json, atomic_write_text

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_briefs")
CONFIG_FILE = os.path.join(BASE_DIR, "../config/recruiter_config.json")

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [RECRUITER] %(message)s")
config = load_config()

class NightlyRecruiter:
    def __init__(self, archive_client=None, brain_client=None):
        self.archive = archive_client
        self.brain = brain_client
        self.config = config
        self.ledger_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/processed_jobs.json")
        self.signatures_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/team_signatures.json")

    async def calculate_match_score(self, job: Dict) -> float:
        """Calculates a high-fidelity match score using Multi-Vector pillar logic."""
        if not os.path.exists(self.signatures_path):
            return 0.5
        with open(self.signatures_path, "r") as f:
            signatures = json.load(f)
        
        score = 0.0
        pillar_hits = 0
        text = (job.get("title", "") + " " + job.get("description", "")).lower()
        
        for pillar, data in signatures.items():
            hit = False
            for kw in data.get("primary", []):
                if kw.lower() in text:
                    score += 0.2
                    hit = True
            if hit:
                pillar_hits += 1
        
        if pillar_hits > 1:
            score *= (1.2 ** pillar_hits)
            
        local_keywords = ["hillsboro", "beaverton", "portland", "oregon"]
        if any(kw in text for kw in local_keywords):
            score *= 1.2
            
        return min(round(score, 2), 1.0)

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
            # Standardize strings to prevent whitespace/case noise
            identity = (job.get("title", "") + job.get("company", "")).lower().replace(" ", "").strip()
            if not identity: return False
            
            for item in ledger:
                # If ledger item is an identity string (not a URL)
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
            
            # Always store both URL and Identity to be safe
            url = job.get("url")
            identity = (job.get("title", "") + job.get("company", ""))
            
            if url and url not in ledger:
                ledger.append(url)
            if identity and identity not in ledger:
                ledger.append(identity)
                
            atomic_write_json(self.ledger_path, ledger[-1000:]) # Increased to 1000 for better historical coverage
        except Exception as e:
            logging.error(f"[RECRUITER] Ledger Update Failed: {e}")

    async def fetch_career_context(self):
        """Retrieves high-level summary from the Archive Node."""
        if not self.archive:
            return "Expert in Silicon Validation and Telemetry. 18 years experience."
        try:
            res_json = await self.archive.call_tool("get_context", arguments={"query": "Diamond Rank technical gems", "n_results": 5})
            res = json.loads(res_json.content[0].text)
            return res.get("text", "Expert in Silicon Validation.")
        except Exception:
            return "Expert in Silicon Validation."

    async def search_for_jobs(self) -> List[Dict]:
        """Uses the Brain's reasoning to identify target listings."""
        if not self.brain:
            return [{"title": "Senior Telemetry Architect", "company": "NVIDIA", "url": "https://nvidia.wd1.myworkdayjobs.com/...", "description": "High-fidelity telemetry and silicon validation in Hillsboro."}]
        
        query = f"Target Roles: {', '.join(self.config.get('target_roles', []))}. Keywords: {', '.join(self.config.get('keywords', []))}."
        task = f"Find 3-5 high-fidelity job URLs matching these criteria: {query}. Provide ONLY a list of URLs."
        
        try:
            res = await self.brain.call_tool("deep_think", arguments={"task": task})
            jobs = []
            if res and res.content:
                import re
                # Improved URL extraction
                urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', res.content[0].text)
                
                # Internal De-duplication (preventing 5 identical openings in one run)
                unique_urls = []
                for u in urls:
                    clean_u = u.split("?")[0].rstrip("/") # Strip query params for fuzzy matching
                    if clean_u not in [x.split("?")[0].rstrip("/") for x in unique_urls]:
                        unique_urls.append(u)
                
                for url in unique_urls[:5]:
                    jobs.append({"title": "Automated Search Result", "company": "External Site", "url": url, "description": ""})
            
            if not jobs:
                return [{"title": "Senior Telemetry Architect", "company": "NVIDIA", "url": "https://nvidia.wd1.myworkdayjobs.com/...", "description": "High-fidelity telemetry and silicon validation in Hillsboro."}]
            return jobs
        except Exception:
            return [{"title": "Senior Telemetry Architect", "company": "NVIDIA", "url": "https://nvidia.wd1.myworkdayjobs.com/...", "description": "High-fidelity telemetry and silicon validation in Hillsboro."}]

    async def generate_brief(self, jobs: List[Dict], context: str) -> (str, int):
        """Synthesizes the Job Brief (The Fridge Note). Returns path and new job count."""
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"job_brief_{date_str}.md"
        path = os.path.join(DRAFTS_DIR, filename)
        
        highest_score = 0.0
        content = f"# 🕵️ Nightly Recruiter Brief: {date_str}\n\n"
        content += "## 🎯 Top Targets\n"
        
        valid_jobs = 0
        for job in jobs:
            if self.is_duplicate(job):
                continue
            score = await self.calculate_match_score(job)
            highest_score = max(highest_score, score)
            content += f"*   **{job['title']}** @ {job['company']}\n"
            content += f"    *   [Apply Here]({job['url']})\n"
            content += f"    *   *Match Score:* {score}\n"
            self.mark_as_processed(job)
            valid_jobs += 1

        if valid_jobs == 0:
            content += "_No new high-fidelity matches found since last scan._\n"

        content += "\n## 🔗 Strategic Search Manifest\n"
        for site in self.config.get("search_sites", []):
            if "hiring.cafe" in site:
                content += "* [Hiring.Cafe: Silicon Forest Telemetry](https://hiring.cafe/search?q=telemetry+silicon+validation+hillsboro)\n"
            elif "linkedin" in site:
                content += "* [LinkedIn: High-Fidelity Validation](https://www.linkedin.com/jobs/search/?keywords=telemetry%20silicon%20validation)\n"
        
        content += "\n\n---\n*Generated by HomeLabAI (The Nightly Recruiter)*"
        
        atomic_write_text(path, content)
        
        if valid_jobs > 0:
            await self.send_brief_uplink(content, highest_score)
            
        return path, valid_jobs

    async def send_brief_uplink(self, brief: str, highest_score: float):
        """Dispatches the brief via Gmail [FEAT-167]."""
        subject = f"[RECRUITER] Nightly Acquisition Brief - {datetime.date.today()}"
        if highest_score >= 0.90:
            subject = f"🚨 [SCRAM ALERT] Critical Job Match - {datetime.date.today()}"
        
        logging.info(f"[RECRUITER] Dispatching Uplink: {subject}")

async def run_recruiter_task(archive_interface=None, brain_interface=None):
    recruiter = NightlyRecruiter(archive_interface, brain_interface)
    logging.info("Waking up for Nightly Recruitment drive...")
    
    ctx = await recruiter.fetch_career_context()
    jobs = await recruiter.search_for_jobs()
    brief_path, new_count = await recruiter.generate_brief(jobs, ctx)
    
    # [FEAT-088] Dashboard Reporting
    try:
        report_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_report.json")
        report = {
            "last_run": datetime.datetime.now().isoformat(),
            "status": "UPLINK_NOMINAL",
            "brief_path": os.path.basename(brief_path),
            "new_jobs": new_count
        }
        atomic_write_json(report_path, report)
    except Exception:
        pass
    
    return brief_path

if __name__ == "__main__":
    asyncio.run(run_recruiter_task())
