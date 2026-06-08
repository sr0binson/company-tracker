import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "companies.db")

COMPANIES = [
    {
        "slug": "posthog",
        "name": "PostHog",
        "description": "Open-source product analytics for developer-focused startups.",
        "customers": "YCombinator,Supabase,Lovable,Mintlify,11x",
        "customer_source": "https://posthog.com/customers",
        "color": "#E8E0D0"
    },
    {
        "slug": "zapier",
        "name": "Zapier",
        "description": "No-code workflow automation for businesses.",
        "customers": "Remote,Miro,Otter.ai,Superhuman,Vendavo",
        "customer_source": "https://zapier.com/customer-stories",
        "color": "#FF7A3D"
    },
    {
        "slug": "linear",
        "name": "Linear",
        "description": "Issue tracking and project management for product and engineering teams.",
        "customers": "OpenAI,Ramp,Mercury,Cohere,Render",
        "customer_source": "https://linear.app/customers",
        "color": "#8B94E0"
    },
    {
        "slug": "replit",
        "name": "Replit",
        "description": "Cloud-based IDE for developers and non-engineers at enterprises.",
        "customers": "Zillow,Databricks,PayPal,Adobe,Talkdesk",
        "customer_source": "https://replit.com/customers",
        "color": "#AAAAAA"
    },
]

def populate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            customers TEXT,
            customer_source TEXT,
            color TEXT
        )
    """)

    for c in COMPANIES:
        cur.execute("""
            INSERT OR IGNORE INTO companies
                (slug, name, description, customers, customer_source, color)
            VALUES
                (:slug, :name, :description, :customers, :customer_source, :color)
        """, c)

    conn.commit()
    conn.close()
    print(f"companies.db populated at {DB_PATH}")

if __name__ == "__main__":
    populate()
