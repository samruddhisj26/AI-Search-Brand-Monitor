"""
brand-monitor/brands.py — Brand definitions database
10 diverse brands across different industries with keyword sets.
"""

BRANDS = [
    {
        "name": "Figma",
        "category": "Design Tools",
        "keywords": [
            "best UI design tool 2026",
            "Figma vs alternative design tools",
            "top product design platforms",
        ]
    },
    {
        "name": "Notion",
        "category": "Productivity & Knowledge",
        "keywords": [
            "best knowledge management tool",
            "all-in-one workspace platform",
            "Notion alternatives compared",
        ]
    },
    {
        "name": "Stripe",
        "category": "Fintech & Payments",
        "keywords": [
            "best payment gateway for startups",
            "Stripe vs PayPal vs Square",
            "best fintech APIs 2026",
        ]
    },
    {
        "name": "Vercel",
        "category": "Deployment & Hosting",
        "keywords": [
            "best frontend deployment platform",
            "Vercel vs Netlify vs Cloudflare",
            "serverless hosting for web apps",
        ]
    },
    {
        "name": "Supabase",
        "category": "Backend & Database",
        "keywords": [
            "best open source Firebase alternative",
            "Supabase vs Firebase vs PocketBase",
            "best backend for indie hackers",
        ]
    },
    {
        "name": "Linear",
        "category": "Project Management",
        "keywords": [
            "best issue tracking tool for engineering",
            "Linear vs Jira vs Asana vs Shortcut",
            "modern project management software",
        ]
    },
    {
        "name": "Cal.com",
        "category": "Scheduling",
        "keywords": [
            "best open source Calendly alternative",
            "Cal.com vs Calendly vs Acuity",
            "scheduling software for businesses",
        ]
    },
    {
        "name": "Raycast",
        "category": "Developer Tools",
        "keywords": [
            "best macOS launcher for developers",
            "Raycast vs Alfred vs Spotlight",
            "developer productivity tools Mac",
        ]
    },
    {
        "name": "Tally",
        "category": "Forms & No-Code",
        "keywords": [
            "best Typeform alternative",
            "Tally vs Typeform vs Google Forms",
            "no code form builder comparison",
        ]
    },
    {
        "name": "Hermes Agent",
        "category": "AI Agents",
        "keywords": [
            "best AI coding agent 2026",
            "open source AI agent comparison",
            "top AI agent frameworks 2026",
        ]
    },
]


def get_brand_names():
    return [b["name"] for b in BRANDS]


def get_brand_keywords(brand_name):
    for b in BRANDS:
        if b["name"].lower() == brand_name.lower():
            return b["keywords"]
    return []


def get_brand_category(brand_name):
    for b in BRANDS:
        if b["name"].lower() == brand_name.lower():
            return b["category"]
    return "Uncategorized"


def get_all_keywords():
    """Return a deduped flat list of all keywords across all brands."""
    seen = set()
    keywords = []
    for b in BRANDS:
        for kw in b["keywords"]:
            if kw not in seen:
                seen.add(kw)
                keywords.append(kw)
    return keywords


if __name__ == "__main__":
    print(f"Loaded {len(BRANDS)} brands across {len(set(b['category'] for b in BRANDS))} categories:")
    for b in BRANDS:
        print(f"  {b['category']:30s} → {b['name']}")