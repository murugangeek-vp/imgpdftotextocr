// MongoDB Initialization Script for OCR Platform
// Runs automatically when MongoDB container starts

db = db.getSiblingDB('ocrplatform');

// ── Collections & Indexes ─────────────────────────────────────────────────────

// ocr_jobs: primary job tracking collection
db.createCollection('ocr_jobs');
db.ocr_jobs.createIndex({ job_id: 1 }, { unique: true });
db.ocr_jobs.createIndex({ user_id: 1, submitted_at: -1 });
db.ocr_jobs.createIndex({ status: 1 });
db.ocr_jobs.createIndex({ file_hash: 1 }); // dedup index
db.ocr_jobs.createIndex({ submitted_at: 1 }, { expireAfterSeconds: 7776000 }); // 90-day TTL

// tier_configs: dynamic tier configuration (hot-reloadable)
db.createCollection('tier_configs');
db.tier_configs.createIndex({ tier: 1 }, { unique: true });

// api_keys: API key authentication
db.createCollection('api_keys');
db.api_keys.createIndex({ api_key: 1 }, { unique: true });
db.api_keys.createIndex({ user_id: 1 });

// users: user accounts
db.createCollection('users');
db.users.createIndex({ user_id: 1 }, { unique: true });
db.users.createIndex({ email: 1 }, { unique: true });

// ── Seed Tier Configs ─────────────────────────────────────────────────────────

db.tier_configs.insertMany([
  {
    tier: "free",
    version: 1,
    limits: {
      pages_per_session: 5,
      pages_per_day: 5,
      pages_per_week: 20,
      pages_per_month: 50,
      max_file_size_mb: 10,
      max_pages_per_pdf: 5,
      concurrent_sessions: 1,
      result_retention_hours: 24
    },
    updated_at: new Date()
  },
  {
    tier: "basic",
    version: 1,
    limits: {
      pages_per_session: 20,
      pages_per_day: 100,
      pages_per_week: 500,
      pages_per_month: 2000,
      max_file_size_mb: 50,
      max_pages_per_pdf: 5,
      concurrent_sessions: 5,
      result_retention_days: 30
    },
    updated_at: new Date()
  },
  {
    tier: "pro",
    version: 1,
    limits: {
      pages_per_session: -1,
      pages_per_day: -1,
      pages_per_week: -1,
      pages_per_month: -1,
      max_file_size_mb: 100,
      max_pages_per_pdf: 5,
      concurrent_sessions: 20,
      result_retention_days: 90
    },
    updated_at: new Date()
  }
]);

// ── Seed Dev API Key ──────────────────────────────────────────────────────────
db.api_keys.insertOne({
  api_key: "dev-api-key-12345",
  user_id: "dev-user-id",
  email: "dev@example.com",
  tier: "pro",
  roles: ["user", "pro"],
  active: true,
  created_at: new Date()
});

print("✅ MongoDB initialized: collections, indexes, and tier configs seeded.");
