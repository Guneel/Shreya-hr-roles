"""Discover publicly indexed role links; never sign into or bypass job boards."""
from datetime import datetime, timezone, timedelta
from html import unescape
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "jobs.json"
QUERIES = {
    "LinkedIn": [
        "site:linkedin.com/jobs/view Bengaluru Workday HRIS",
        "site:linkedin.com/jobs/view Bengaluru SAP SuccessFactors HRIS",
        "site:linkedin.com/jobs/view Bengaluru compensation rewards HR",
    ],
    "Naukri": [
        "site:naukri.com/job-listings Bengaluru HRIS Workday SAP SuccessFactors",
        "site:naukri.com/job-listings Bengaluru compensation benefits HR",
    ],
    "iimjobs": [
        "site:iimjobs.com Bengaluru HRIS Workday SAP SuccessFactors",
        "site:iimjobs.com Bengaluru compensation rewards benefits HR",
    ],
}
TERMS = ("hris", "workday", "sap", "successfactor", "compensation", "reward", "benefit", "hcm")

def clean(value):
    return re.sub(r"\\s+", " ", unescape(re.sub(r"<[^>]+>", "", value))).strip()

def extract(html):
    found = []
    # Search results provide a public title and a link back to the job board.
    pattern = r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    for href, title in re.findall(pattern, html, re.S):
        href = unescape(href)
        destination = parse_qs(urlparse(href).query).get("uddg", [href])[0]
        if destination.startswith("http"):
            found.append((clean(title), destination))
    return found

def role_family(title):
    text = title.lower()
    if "workday" in text:
        return "Workday / HRIS"
    if "sap" in text or "successfactor" in text:
        return "SAP SuccessFactors"
    if any(word in text for word in ("compensation", "reward", "benefit")):
        return "Rewards / Compensation"
    return "HRIS / HR Technology"

def main():
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    known = {job["url"].split("?")[0] for job in payload.get("jobs", [])}
    discovered = []
    for source, queries in QUERIES.items():
        for query in queries:
            request = Request(
                "https://html.duckduckgo.com/html/?q=" + quote_plus(query),
                headers={"User-Agent": "Mozilla/5.0 (compatible; HRRoleRadar/1.0)"},
            )
            try:
                with urlopen(request, timeout=25) as response:
                    html = response.read().decode("utf-8", "replace")
                for title, url in extract(html):
                    canonical = url.split("?")[0]
                    lower = title.lower()
                    if canonical in known or not any(term in lower for term in TERMS):
                        continue
                    known.add(canonical)
                    discovered.append({
                        "title": title, "company": "See source posting",
                        "location": "Bengaluru — verify in posting",
                        "focus": role_family(title), "fit": "Review",
                        "posted": "New search result — verify date", "source": source,
                        "url": url, "why": "Found in today's public search; verify role scope and location.",
                        "status": "Research",
                        "notes": "Confirm this is active, Bengaluru-based, and process-focused before applying."
                    })
            except Exception as error:
                print(f"Search unavailable for {source}: {error}")
    payload["jobs"] = (discovered + payload.get("jobs", []))[:100]
    payload["updatedAt"] = datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(timespec="seconds")
    DATA.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
    print(f"Added {len(discovered)} new results; retained {len(payload['jobs'])} total roles.")

if __name__ == "__main__":
    main()