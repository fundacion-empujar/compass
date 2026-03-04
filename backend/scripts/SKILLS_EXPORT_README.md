# Skills Export Scripts

These scripts allow you to extract skills data by user from the Brujula MongoDB database.

## Overview

The scripts extract skills that have been discovered and extracted during user conversations from the `explore_experiences_director_state` collection in the application database.

## Available Scripts

### 1. JSON Export (`export_user_skills.py`)
Exports skills data in a hierarchical JSON format showing users, their experiences, and extracted skills.

**Output format:**
```json
{
  "export_date": "2025-12-16T17:22:33.588577",
  "total_users": 25,
  "database": "compass-application-dev-brujula",
  "data": [
    {
      "session_id": 153957396055258,
      "experiences": [
        {
          "experience_uuid": "...",
          "experience_title": "...",
          "skills": [
            {
              "skill_uuid": "...",
              "skill_model_id": "...",
              "preferred_label": "...",
              "rank": null
            }
          ]
        }
      ]
    }
  ]
}
```

### 2. CSV Export (`export_user_skills_csv.py`)
Exports skills data in a flat CSV format suitable for analysis in Excel, Google Sheets, or data analysis tools.

**CSV columns:**
- `session_id`: User session identifier
- `user_id`: Unique user identifier (Firebase UID)
- `user_created_at`: When the user account was created (ISO 8601 timestamp)
- `session_timestamp`: When the conversation session was conducted (ISO 8601 timestamp)
- `experience_uuid`: Unique identifier for the experience
- `experience_title`: Title/description of the experience
- `skill_rank`: Rank of the skill within the experience (1-8 typically)
- `skill_uuid`: Unique identifier for the skill
- `skill_model_id`: Model ID from the taxonomy
- `skill_preferred_label`: Human-readable skill name

## Prerequisites

1. MongoDB connection credentials (already in your `.env` file)
2. Python environment with required dependencies

## Setup

Make sure you're in the backend directory with the virtual environment activated:

```bash
cd /Users/nraffa/projects/worldbank/empujar-fork/compass/backend
source venv-backend/bin/activate
```

## Usage

### JSON Export

```bash
# Export to default file (user_skills_export.json)
python scripts/export_user_skills.py

# Export to custom file
python scripts/export_user_skills.py --output my_skills_data.json
```

### CSV Export

```bash
# Export to default file (user_skills_export.csv)
python scripts/export_user_skills_csv.py

# Export to custom file
python scripts/export_user_skills_csv.py --output my_skills_data.csv
```

## Environment Variables Required

The scripts read from your `.env` file and require:

- `APPLICATION_MONGODB_URI`: MongoDB connection string for application database
- `APPLICATION_DATABASE_NAME`: Application database name (e.g., "compass-application-dev-brujula")
- `TAXONOMY_MONGODB_URI`: MongoDB connection string for taxonomy database (JSON export only)
- `TAXONOMY_DATABASE_NAME`: Taxonomy database name (JSON export only)

## About User Email

**Important:** User email addresses are **NOT** included in the export because:

1. **Not stored in MongoDB**: Email addresses are only present in Firebase authentication tokens at runtime
2. **Privacy by design**: The sysession identifiers)
- ✅ **User IDs** (Firebase UIDs - pseudo-anonymous)
- ✅ **Timestamps** (account creation and session timestamps)
- ✅ **Skill UUIDs and labels** (from ESCO taxonomy - public data)
- ✅ **Experience UUIDs** (anonymized experience identifiers)
- ⚠️ **Experience titles** (may contain user-provided text)
- ❌ **Email addresses** (not stored in database, not included
- `user_id`: Firebase UID (e.g., "i3bhBzybzOQnmOJFn6brTI225482")
- `user_created_at`: Account creation timestamp
- `session_timestamp`: When the conversation happened

If you need to correlate user_ids with emails, you would need to:
1. Access Firebase Authentication directly (requires Firebase Admin SDK)
2. Use the user_id to look up the email in Firebase
3. This typically requires proper authentication and authorization

## Data Privacy & Sharing

### Is this data shareable?

**Current status:** The extracted data contains:
- ✅ **Session IDs** (anonymized user identifiers)
- ✅ **Skill UUIDs and labels** (from ESCO taxonomy - public data)
- ✅ **Experience UUIDs** (anonymized experience identifiers)
- ⚠️ **Experience titles** (may contain user-provided text)

**Before sharing:**
1. Review experience titles to ensure no personally identifiable information (PII)
2. Consider removing or redacting the `experience_title` column if needed
3. Session IDs are pseudo-anonymous but could potentially be linked back to users in your system

**Recommendation:** 
- The skills data itself (UUIDs and labels) is safe to share as it's from public ESCO taxonomy
- For full anonymization, remove or hash the `experience_title` field
- Aggregate statistics (e.g., "most common skills") are completely safe to share

## Sample Statistics

From the current Brujula testing database:
- **Total unique sessions:** 25 users
- **Total unique experiences:** 61 work experiences
- **Total skill extractions:** 479 skills

## Data Source

**Database:** compass-application-dev-brujula (Brujula testing environment)  
**Collection:** `explore_experiences_director_state`  
**What it contains:** Skills extracted from user conversations about their work experiences

Each user conversation session generates experiences, and for each experience, the system extracts relevant skills from the ESCO taxonomy based on what the user described.

## Troubleshooting

### Connection Issues
If you get connection errors, verify your MongoDB credentials in the `.env` file.

### No Data Exported
This could mean:
- No users have completed the experience exploration phase
- Database connection is pointing to wrong environment
- Collection name has changed

### Permission Issues
Make sure the MongoDB user has read permissions on the application database.

## Additional Analysis

You can use these exports for:
- Analyzing which skills are most commonly extracted
- Understanding user experience patterns
- Validating skill extraction quality
- Training data for ML models
- Reporting and dashboards
