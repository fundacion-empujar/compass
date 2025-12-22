#!/usr/bin/env python3
"""
Export skills extracted by users to CSV format for easy analysis.

This script extracts all skills that have been discovered/extracted per user session
and exports them in a flat CSV format.
"""

import asyncio
import csv
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Settings:
    """Settings for the export script"""
    application_mongodb_uri: str = os.getenv("APPLICATION_MONGODB_URI", "")
    application_database_name: str = os.getenv("APPLICATION_DATABASE_NAME", "")
    
    def validate(self):
        """Validate that all required settings are present"""
        if not self.application_mongodb_uri:
            raise ValueError("APPLICATION_MONGODB_URI is required")
        if not self.application_database_name:
            raise ValueError("APPLICATION_DATABASE_NAME is required")


async def extract_skills_to_csv(output_file: str = "user_skills_export.csv"):
    """
    Extract all skills by user to CSV format.
    
    Args:
        output_file: Path to output CSV file
    """
    settings = Settings()
    settings.validate()
    
    logger.info("Connecting to MongoDB...")
    
    # Connect to database
    app_client = AsyncIOMotorClient(settings.application_mongodb_uri)
    app_db = app_client[settings.application_database_name]
    
    try:
        # Get the explore experiences collection
        explore_experiences_collection = app_db.get_collection("explore_experiences_director_state")
        user_preferences_collection = app_db.get_collection("user_preferences")
        agent_director_state_collection = app_db.get_collection("agent_director_state")
        
        # Get all explore experiences states
        logger.info("Fetching explore experiences states...")
        experiences_states = await explore_experiences_collection.find({}).to_list(length=None)
        logger.info(f"Found {len(experiences_states)} explore experiences states")
        
        # Get all user preferences to map session_id to user_id
        logger.info("Fetching user preferences...")
        user_preferences = await user_preferences_collection.find({}).to_list(length=None)
        
        # Create mapping of session_id -> user info
        session_to_user = {}
        for pref in user_preferences:
            user_id = pref.get("user_id")
            sessions = pref.get("sessions", [])
            user_created_at = pref.get("created_at")
            for session_id in sessions:
                session_to_user[session_id] = {
                    "user_id": user_id,
                    "user_created_at": user_created_at.isoformat() if user_created_at else None
                }
        
        # Get all agent director states for session timestamps
        logger.info("Fetching session timestamps...")
        agent_states = await agent_director_state_collection.find({}).to_list(length=None)
        session_timestamps = {}
        for state in agent_states:
            session_id = state.get("session_id")
            conducted_at = state.get("conversation_conducted_at")
            if session_id and conducted_at:
                session_timestamps[session_id] = conducted_at.isoformat() if conducted_at else None
        
        # Extract skills data
        csv_rows = []
        
        for state_doc in experiences_states:
            session_id = state_doc.get("session_id")
            experiences_state = state_doc.get("experiences_state", {})
            
            # Get user info for this session
            user_info = session_to_user.get(session_id, {})
            session_timestamp = session_timestamps.get(session_id)
            
            # Process each experience
            for exp_uuid, exp_state in experiences_state.items():
                experience = exp_state.get("experience", {})
                top_skills = experience.get("top_skills", [])
                experience_title = experience.get("experience_title") or experience.get("title", "")
                
                if top_skills:
                    for idx, skill in enumerate(top_skills, 1):
                        row = {
                            "session_id": session_id,
                            "user_id": user_info.get("user_id", ""),
                            "user_created_at": user_info.get("user_created_at", ""),
                            "session_timestamp": session_timestamp or "",
                            "experience_uuid": exp_uuid,
                            "experience_title": experience_title,
                            "skill_rank": idx,
                            "skill_uuid": skill.get("UUID", ""),
                            "skill_model_id": skill.get("modelId", ""),
                            "skill_preferred_label": skill.get("preferredLabel", ""),
                        }
                        csv_rows.append(row)
        
        # Write to CSV
        logger.info(f"Writing {len(csv_rows)} rows to {output_file}...")
        
        if csv_rows:
            fieldnames = [
                "session_id",
                "user_id",
                "user_created_at",
                "session_timestamp",
                "experience_uuid",
                "experience_title",
                "skill_rank",
                "skill_uuid",
                "skill_model_id",
                "skill_preferred_label"
            ]
            
            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(csv_rows)
            
            logger.info(f"✓ Export complete! Data saved to {output_file}")
            
            # Print summary
            unique_sessions = len(set(row["session_id"] for row in csv_rows))
            unique_experiences = len(set(row["experience_uuid"] for row in csv_rows))
            
            logger.info(f"\nSummary:")
            logger.info(f"  Total unique sessions: {unique_sessions}")
            logger.info(f"  Total unique experiences: {unique_experiences}")
            logger.info(f"  Total skill extractions: {len(csv_rows)}")
        else:
            logger.warning("No skills data found to export")
        
    finally:
        # Close connections
        app_client.close()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Export skills extracted by users to CSV format",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="user_skills_export.csv",
        help="Output CSV file path (default: user_skills_export.csv)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(extract_skills_to_csv(args.output))


if __name__ == "__main__":
    main()
