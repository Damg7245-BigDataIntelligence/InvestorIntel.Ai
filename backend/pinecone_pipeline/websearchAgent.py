# To install dependencies:
# pip install tavily-python python-dotenv

from tavily import TavilyClient
from dotenv import load_dotenv
import os
import datetime

# Load environment variables from .env file
load_dotenv()

# Tavily API Key from .env
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
if not TAVILY_API_KEY:
    raise ValueError("TAVILY_API_KEY is missing from .env file.")

# Predefined trusted domains for filtering results
TRUSTED_DOMAINS = [
    "techcrunch.com",           # TechCrunch – Startup & Tech
    "crunchbase.com",           # Crunchbase News – Funding & VC
    "cbinsights.com",           # CB Insights – Market Intelligence
    "businessinsider.com",      # Business Insider – Business & Industry
    "bloomberg.com",            # Bloomberg – Finance, Tech
    "forbes.com",               # Forbes – Startups, Business
    "theinformation.com",       # The Information – Premium Tech News
    "fastcompany.com",          # Fast Company – Innovation & Design
    "hbr.org",                  # Harvard Business Review – Strategy & Trends
    "skift.com"                 # Skift – Travel Industry Insights
    "twitter.com",              # for official tweets, threads, news announcements
    "linkedin.com",             # for company posts, founder updates
]


def base_search(query, include_domains=None):
    client = TavilyClient(TAVILY_API_KEY)
    params = {
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "max_results": 5
    }
    if include_domains:
        params["include_domains"] = include_domains
    return client.search(**params)


def is_relevant(results, startup_name):
    if not results:
        return False
    items = results.get("results", []) if isinstance(results, dict) else results
    name = startup_name.lower()
    for r in items:
        text = (r.get("title", "") + " " + r.get("content", "")).lower()
        if name in text:
            return True
    return False


def search_with_fallback(startup_name, industry):
    include = TRUSTED_DOMAINS

    # 1) startup-specific
    startup_query = f"recent innovations and market trends 2025 for {startup_name}"
    res = base_search(startup_query, include_domains=include)
    if not is_relevant(res, startup_name):
        print(f"No relevant startup-specific results found for '{startup_name}'. Falling back to industry search.")
        # 2) fallback
        industry_query = f"{industry} industry trends recent news US market"
        res = base_search(industry_query, include_domains=include)
        search_type = "Industry-Based"
    else:
        search_type = "Startup-Specific"

    return res, search_type


if __name__ == "__main__":
    # Hard-coded for testing
    startup_name = "Tesla"
    industry = "AI"

    results, search_type = search_with_fallback(startup_name, industry)
    items = results.get("results", []) if isinstance(results, dict) else results

    print(f"\nSearch Type: {search_type}\n")
    for i, r in enumerate(items, start=1):
        title = str(r.get("title", ""))
        url = str(r.get("url", ""))

        print(f"{i}. {title}")
        print("  Type of title:", type(title))
        print(f"   Link: {url}")
        print("  Type of url:", type(url))
        print()
