"""
Seed script: integration connectors + subscription plans.
Run: python -m scripts.seed_data
"""
import asyncio, sys, uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.database import DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

NOW = datetime.utcnow()


CONNECTORS = [
    # CRM
    {"slug": "salesforce",        "name": "Salesforce",           "category": "crm",           "auth_type": "oauth2",  "description": "Sync contacts, leads, and opportunities with Salesforce CRM",         "base_url": "https://api.salesforce.com",        "auth_config": {"oauth_url": "https://login.salesforce.com/services/oauth2/authorize", "token_url": "https://login.salesforce.com/services/oauth2/token", "scopes": ["api", "refresh_token"], "test_endpoint": "/services/data/v58.0/"}, "rate_limit_per_minute": 100},
    {"slug": "hubspot",           "name": "HubSpot",              "category": "crm",           "auth_type": "oauth2",  "description": "CRM contacts, deals, and pipeline management",                       "base_url": "https://api.hubapi.com",            "auth_config": {"oauth_url": "https://app.hubspot.com/oauth/authorize", "token_url": "https://api.hubapi.com/oauth/v1/token", "scopes": ["contacts", "crm.objects.deals.read"], "test_endpoint": "/crm/v3/objects/contacts"}, "rate_limit_per_minute": 100},
    {"slug": "pipedrive",         "name": "Pipedrive",            "category": "crm",           "auth_type": "oauth2",  "description": "Sales pipeline CRM to track deals and contacts from voice calls",    "base_url": "https://api.pipedrive.com",         "auth_config": {"oauth_url": "https://oauth.pipedrive.com/oauth/authorize", "token_url": "https://oauth.pipedrive.com/oauth/token", "scopes": ["deals:full", "contacts:full"], "test_endpoint": "/v1/users/me"}, "rate_limit_per_minute": 80},
    {"slug": "zendesk",           "name": "Zendesk",              "category": "crm",           "auth_type": "oauth2",  "description": "Create and update support tickets from voice interactions",           "base_url": "https://api.zendesk.com",           "auth_config": {"test_endpoint": "/api/v2/users/me.json"}, "rate_limit_per_minute": 100},
    {"slug": "intercom",          "name": "Intercom",             "category": "crm",           "auth_type": "oauth2",  "description": "Create conversations and update contacts in Intercom from calls",    "base_url": "https://api.intercom.io",           "auth_config": {"oauth_url": "https://app.intercom.com/oauth", "token_url": "https://api.intercom.io/auth/eagle/token", "scopes": ["read_conversations", "write_conversations"], "test_endpoint": "/me"}, "rate_limit_per_minute": 60},
    # Calendar
    {"slug": "google-calendar",   "name": "Google Calendar",      "category": "calendar",      "auth_type": "oauth2",  "description": "Schedule and manage calendar events during voice calls",             "base_url": "https://www.googleapis.com",        "auth_config": {"oauth_url": "https://accounts.google.com/o/oauth2/v2/auth", "token_url": "https://oauth2.googleapis.com/token", "scopes": ["https://www.googleapis.com/auth/calendar"], "test_endpoint": "/calendar/v3/users/me/calendarList"}, "rate_limit_per_minute": 60},
    {"slug": "calendly",          "name": "Calendly",             "category": "calendar",      "auth_type": "oauth2",  "description": "Book appointments with Calendly scheduling",                         "base_url": "https://api.calendly.com",          "auth_config": {"oauth_url": "https://auth.calendly.com/oauth/authorize", "token_url": "https://auth.calendly.com/oauth/token", "scopes": ["default"], "test_endpoint": "/users/me"}, "rate_limit_per_minute": 60},
    {"slug": "cal-com",           "name": "Cal.com",              "category": "calendar",      "auth_type": "api_key", "description": "Open-source scheduling — book meetings directly from voice calls",   "base_url": "https://api.cal.com",              "auth_config": {"api_key_location": "query", "api_key_name": "apiKey", "test_endpoint": "/v1/me"}, "rate_limit_per_minute": 60},
    # Communication
    {"slug": "slack",             "name": "Slack",                "category": "communication", "auth_type": "oauth2",  "description": "Send notifications and messages to Slack channels",                  "base_url": "https://slack.com/api",             "auth_config": {"oauth_url": "https://slack.com/oauth/v2/authorize", "token_url": "https://slack.com/api/oauth.v2.access", "scopes": ["chat:write", "channels:read"], "test_endpoint": "/auth.test"}, "rate_limit_per_minute": 60},
    {"slug": "microsoft-teams",   "name": "Microsoft Teams",      "category": "communication", "auth_type": "oauth2",  "description": "Send messages and notifications to Teams channels",                  "base_url": "https://graph.microsoft.com",       "auth_config": {"oauth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token", "scopes": ["ChannelMessage.Send", "Chat.ReadWrite"], "test_endpoint": "/v1.0/me"}, "rate_limit_per_minute": 60},
    {"slug": "twilio",            "name": "Twilio",               "category": "communication", "auth_type": "api_key", "description": "Enhanced telephony, SMS and WhatsApp messaging",                     "base_url": "https://api.twilio.com",            "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Basic {api_key}", "test_endpoint": "/2010-04-01/Accounts.json"}, "rate_limit_per_minute": 200},
    {"slug": "sendgrid",          "name": "SendGrid",             "category": "communication", "auth_type": "api_key", "description": "Send transactional emails from voice conversations",                  "base_url": "https://api.sendgrid.com",          "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Bearer {api_key}", "test_endpoint": "/v3/user/profile"}, "rate_limit_per_minute": 100},
    # Productivity / Automation
    {"slug": "zapier",            "name": "Zapier",               "category": "productivity",  "auth_type": "oauth2",  "description": "Connect to 5000+ apps via Zapier automation",                        "base_url": "https://hooks.zapier.com",          "auth_config": {"test_endpoint": "/"}, "rate_limit_per_minute": 100},
    {"slug": "make",              "name": "Make (Integromat)",    "category": "productivity",  "auth_type": "api_key", "description": "Visual automation platform — connect Voicecon to any app",           "base_url": "https://hook.eu1.make.com",         "auth_config": {"api_key_location": "query", "api_key_name": "token", "test_endpoint": "/"}, "rate_limit_per_minute": 100},
    {"slug": "google-sheets",     "name": "Google Sheets",        "category": "productivity",  "auth_type": "oauth2",  "description": "Log call data and customer information to spreadsheets",             "base_url": "https://sheets.googleapis.com",     "auth_config": {"oauth_url": "https://accounts.google.com/o/oauth2/v2/auth", "token_url": "https://oauth2.googleapis.com/token", "scopes": ["https://www.googleapis.com/auth/spreadsheets"], "test_endpoint": "/v4/spreadsheets"}, "rate_limit_per_minute": 60},
    {"slug": "google-drive",      "name": "Google Drive",         "category": "productivity",  "auth_type": "oauth2",  "description": "Save call recordings and transcripts to Google Drive",               "base_url": "https://www.googleapis.com",        "auth_config": {"oauth_url": "https://accounts.google.com/o/oauth2/v2/auth", "token_url": "https://oauth2.googleapis.com/token", "scopes": ["https://www.googleapis.com/auth/drive.file"], "test_endpoint": "/drive/v3/about?fields=user"}, "rate_limit_per_minute": 60},
    {"slug": "airtable",          "name": "Airtable",             "category": "productivity",  "auth_type": "api_key", "description": "Store and organize conversation data in Airtable",                   "base_url": "https://api.airtable.com",          "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Bearer {api_key}", "test_endpoint": "/v0/meta/whoami"}, "rate_limit_per_minute": 60},
    # Payment
    {"slug": "stripe",            "name": "Stripe",               "category": "other",         "auth_type": "api_key", "description": "Process payments and manage subscriptions during calls",             "base_url": "https://api.stripe.com",            "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Bearer {api_key}", "test_endpoint": "/v1/account"}, "rate_limit_per_minute": 100},
    # CRM (extended)
    {"slug": "gohighlevel",       "name": "GoHighLevel",          "category": "crm",           "auth_type": "api_key", "description": "All-in-one CRM — sync contacts, pipelines, and SMS",                "base_url": "https://rest.gohighlevel.com",      "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Bearer {api_key}", "test_endpoint": "/v1/contacts/"}, "rate_limit_per_minute": 100},
    {"slug": "notion",            "name": "Notion",               "category": "productivity",  "auth_type": "oauth2",  "description": "Create and update Notion pages and databases from voice calls",      "base_url": "https://api.notion.com",            "auth_config": {"oauth_url": "https://api.notion.com/v1/oauth/authorize", "token_url": "https://api.notion.com/v1/oauth/token", "scopes": ["read_content", "update_content", "insert_content"], "test_endpoint": "/v1/users/me"}, "rate_limit_per_minute": 60},
    {"slug": "clickup",           "name": "ClickUp",              "category": "productivity",  "auth_type": "oauth2",  "description": "Create and manage ClickUp tasks from voice calls and workflows",     "base_url": "https://api.clickup.com/api/v2",     "auth_config": {"oauth_url": "https://app.clickup.com/api", "token_url": "https://api.clickup.com/api/v2/oauth/token", "scopes": [], "test_endpoint": "/user"}, "rate_limit_per_minute": 100},
    {"slug": "trello",            "name": "Trello",               "category": "productivity",  "auth_type": "api_key", "description": "Create and manage Trello cards, lists, and boards from voice calls",  "base_url": "https://api.trello.com/1",          "auth_config": {"connect_flow": "trello_token", "test_endpoint": "/members/me"}, "rate_limit_per_minute": 100},
    {"slug": "whatsapp",          "name": "WhatsApp",             "category": "communication", "auth_type": "api_key", "description": "Send WhatsApp messages via the WhatsApp Business Cloud API",         "base_url": "https://graph.facebook.com/v18.0",  "auth_config": {"connect_flow": "whatsapp_credentials"}, "rate_limit_per_minute": 60},
    {"slug": "monday",            "name": "Monday.com",           "category": "productivity",  "auth_type": "oauth2",  "description": "Update boards and items in Monday.com from call outcomes",           "base_url": "https://api.monday.com",            "auth_config": {"oauth_url": "https://auth.monday.com/oauth2/authorize", "token_url": "https://auth.monday.com/oauth2/token", "scopes": ["boards:read", "boards:write"], "test_endpoint": "/v2"}, "rate_limit_per_minute": 60},
    # Phone Providers
    {"slug": "telnyx",            "name": "Telnyx",               "category": "phone",         "auth_type": "api_key", "description": "Carrier-grade VoIP and SIP trunking for voice AI deployments",      "base_url": "https://api.telnyx.com",            "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Bearer {api_key}", "test_endpoint": "/v2/phone_numbers"}, "rate_limit_per_minute": 200},
    {"slug": "vonage",            "name": "Vonage (Nexmo)",       "category": "phone",         "auth_type": "api_key", "description": "Global cloud communications — calls, SMS, phone number management", "base_url": "https://api.nexmo.com",             "auth_config": {"api_key_location": "query", "api_key_name": "api_key", "test_endpoint": "/v1/account/get-balance"}, "rate_limit_per_minute": 100},
    # Analytics / Observability
    {"slug": "langfuse",          "name": "Langfuse",             "category": "analytics",     "auth_type": "api_key", "description": "Open-source LLM observability — trace, evaluate, and debug AI",    "base_url": "https://cloud.langfuse.com",        "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Basic {api_key}", "test_endpoint": "/api/public/health"}, "rate_limit_per_minute": 200},
    # Cloud Storage
    {"slug": "aws-s3",            "name": "AWS S3",               "category": "cloud",         "auth_type": "api_key", "description": "Store call recordings and files in Amazon S3 buckets",              "base_url": "https://s3.amazonaws.com",          "auth_config": {"api_key_location": "header", "api_key_name": "X-Amz-Security-Token", "test_endpoint": "/"}, "rate_limit_per_minute": 500},
    {"slug": "azure-blob",        "name": "Azure Blob Storage",   "category": "cloud",         "auth_type": "api_key", "description": "Store and manage call data in Microsoft Azure Blob Storage",         "base_url": "https://blob.core.windows.net",     "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "test_endpoint": "/"}, "rate_limit_per_minute": 500},
    {"slug": "gcs",               "name": "Google Cloud Storage", "category": "cloud",         "auth_type": "api_key", "description": "Store recordings and data in Google Cloud Storage buckets",          "base_url": "https://storage.googleapis.com",    "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Bearer {api_key}", "test_endpoint": "/storage/v1/b"}, "rate_limit_per_minute": 500},
    {"slug": "cloudflare-r2",     "name": "Cloudflare R2",        "category": "cloud",         "auth_type": "api_key", "description": "Zero-egress object storage for recordings and call artifacts",       "base_url": "https://api.cloudflare.com",        "auth_config": {"api_key_location": "header", "api_key_name": "Authorization", "api_key_format": "Bearer {api_key}", "test_endpoint": "/client/v4/user/tokens/verify"}, "rate_limit_per_minute": 200},
    {"slug": "supabase",          "name": "Supabase",             "category": "cloud",         "auth_type": "api_key", "description": "Open-source Firebase alternative — store call data in Postgres",     "base_url": "https://your-project.supabase.co",  "auth_config": {"api_key_location": "header", "api_key_name": "apikey", "test_endpoint": "/rest/v1/"}, "rate_limit_per_minute": 200},
]

PLANS = [
    {"name": "Starter",      "price_monthly": 29,  "price_yearly": 290,  "included_minutes": 1000,  "included_calls": 100,  "max_agents": 2,  "max_phone_numbers": 1,  "max_knowledge_bases": 2,  "overage_rate_per_minute": 0.015, "overage_rate_per_call": 0.05, "features": {"Voice calls": True, "SMS support": True, "Basic analytics": True, "Email support": True}},
    {"name": "Professional", "price_monthly": 99,  "price_yearly": 990,  "included_minutes": 5000,  "included_calls": 500,  "max_agents": 10, "max_phone_numbers": 5,  "max_knowledge_bases": 10, "overage_rate_per_minute": 0.012, "overage_rate_per_call": 0.04, "features": {"Voice calls": True, "SMS support": True, "Advanced analytics": True, "Priority support": True, "Custom workflows": True, "API access": True}},
    {"name": "Enterprise",   "price_monthly": 299, "price_yearly": 2990, "included_minutes": 20000, "included_calls": 2000, "max_agents": 50, "max_phone_numbers": 20, "max_knowledge_bases": 50, "overage_rate_per_minute": 0.01,  "overage_rate_per_call": 0.03, "features": {"Voice calls": True, "SMS support": True, "Advanced analytics": True, "Dedicated support": True, "Custom workflows": True, "API access": True, "White-label": True, "SLA guarantee": True}},
]


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Integration Connectors ─────────────────────────────────────────
        existing_slugs_result = await db.execute(text("SELECT slug FROM integration_connectors"))
        existing_slugs = {row[0] for row in existing_slugs_result.fetchall()}
        new_connectors = [c for c in CONNECTORS if c["slug"] not in existing_slugs]
        if new_connectors:
            print(f"Seeding {len(new_connectors)} new integration connectors...")
            for c in new_connectors:
                await db.execute(text("""
                    INSERT INTO integration_connectors
                    (id, name, slug, category, description, base_url, auth_type, auth_config,
                     supports_triggers, supports_actions, supports_realtime, supports_webhooks,
                     rate_limit_per_minute, is_active, is_beta, is_premium, created_at, updated_at)
                    VALUES (:id, :name, :slug, :category, :description, :base_url, :auth_type, :auth_config,
                            false, true, false, false,
                            :rate_limit, true, false, false, :now, :now)
                    ON CONFLICT (slug) DO NOTHING
                """), {
                    "id": uuid.uuid4().hex,
                    "name": c["name"],
                    "slug": c["slug"],
                    "category": c["category"],
                    "description": c["description"],
                    "base_url": c["base_url"],
                    "auth_type": c["auth_type"],
                    "auth_config": str(c["auth_config"]).replace("'", '"'),
                    "rate_limit": c.get("rate_limit_per_minute", 60),
                    "now": NOW,
                })
            await db.commit()
            print(f"  ✅ Seeded {len(new_connectors)} new connectors ({len(existing_slugs)} already existed)")
        else:
            print(f"  ℹ️  All {len(CONNECTORS)} connectors already seeded")

        # ── Subscription Plans ─────────────────────────────────────────────
        existing = (await db.execute(text("SELECT COUNT(*) FROM subscription_plans"))).scalar()
        if existing == 0:
            print("Seeding subscription plans...")
            import json
            for p in PLANS:
                await db.execute(text("""
                    INSERT INTO subscription_plans
                    (id, name, description, stripe_product_id, stripe_price_id,
                     price_monthly, price_yearly, currency,
                     included_minutes, included_calls, max_agents, max_phone_numbers, max_knowledge_bases,
                     overage_rate_per_minute, overage_rate_per_call,
                     features, is_active, is_public, sort_order, created_at, updated_at)
                    VALUES (:id, :name, :desc, :stripe_pid, :stripe_priceid,
                            :pm, :py, 'usd',
                            :mins, :calls, :agents, :phones, :kbs,
                            :overm, :overc,
                            :features, 1, 1, :sort, :now, :now)
                """), {
                    "id": uuid.uuid4().hex,
                    "name": p["name"],
                    "desc": f"For {p['name'].lower()} users",
                    "stripe_pid": f"prod_{p['name'].lower()}",
                    "stripe_priceid": f"price_{p['name'].lower()}_monthly",
                    "sort": PLANS.index(p) + 1,
                    "pm": p["price_monthly"],
                    "py": p["price_yearly"],
                    "mins": p["included_minutes"],
                    "calls": p["included_calls"],
                    "agents": p["max_agents"],
                    "phones": p["max_phone_numbers"],
                    "kbs": p["max_knowledge_bases"],
                    "overm": p["overage_rate_per_minute"],
                    "overc": p["overage_rate_per_call"],
                    "features": json.dumps(p["features"]),
                    "now": NOW,
                })
            await db.commit()
            print(f"  ✅ Seeded {len(PLANS)} subscription plans")
        else:
            print(f"  ℹ️  Subscription plans already seeded ({existing} rows)")

    print("\n🎉 Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
