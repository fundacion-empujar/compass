#!/usr/bin/env python3
"""
Export skills extracted by users from the Brujula MongoDB database.

This script extracts all skills that have been discovered/extracted per user session
from the explore_experiences_director_state collection.

Environment Variables Required:
  APPLICATION_MONGODB_URI    MongoDB connection URI for application database
  APPLICATION_DATABASE_NAME  Database name
  TAXONOMY_MONGODB_URI       MongoDB connection URI for taxonomy database  
  TAXONOMY_DATABASE_NAME     Taxonomy database name (for skill details)
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# Load environment variables from .env file
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
    taxonomy_mongodb_uri: str = os.getenv("TAXONOMY_MONGODB_URI", "")
    taxonomy_database_name: str = os.getenv("TAXONOMY_DATABASE_NAME", "")
    
    def validate(self):
        """Validate that all required settings are present"""
        if not self.application_mongodb_uri:
            raise ValueError("APPLICATION_MONGODB_URI is required")
        if not self.application_database_name:
            raise ValueError("APPLICATION_DATABASE_NAME is required")
        if not self.taxonomy_mongodb_uri:
            raise ValueError("TAXONOMY_MONGODB_URI is required")
        if not self.taxonomy_database_name:
            raise ValueError("TAXONOMY_DATABASE_NAME is required")


async def extract_skills_by_user(output_file: str = "user_skills_export.json"):
    """
    Extract all skills by user from the MongoDB database.
    
    Args:
        output_file: Path to output JSON file
    """
    settings = Settings()
    settings.validate()
    
    logger.info("Connecting to MongoDB...")
    
    # Connect to databases
    app_client = AsyncIOMotorClient(settings.application_mongodb_uri)
    app_db = app_client[settings.application_database_name]
    
    taxonomy_client = AsyncIOMotorClient(settings.taxonomy_mongodb_uri)
    taxonomy_db = taxonomy_client[settings.taxonomy_database_name]
    
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
        user_skills_data = []
        skill_ids_to_fetch = set()
        
        for state_doc in experiences_states:
            session_id = state_doc.get("session_id")
            experiences_state = state_doc.get("experiences_state", {})
            
            # Get user info for this session
            user_info = session_to_user.get(session_id, {})
            session_timestamp = session_timestamps.get(session_id)
            
            user_record = {
                "session_id": session_id,
                "user_id": user_info.get("user_id"),
                "user_created_at": user_info.get("user_created_at"),
                "session_timestamp": session_timestamp,
                "experiences": []
            }
            
            # Process each experience
            for exp_uuid, exp_state in experiences_state.items():
                experience = exp_state.get("experience", {})
                top_skills = experience.get("top_skills", [])
                
                if top_skills:
                    # experience_title is stored under "experience_title"; keep a fallback to "title"
                    exp_record = {
                        "experience_uuid": exp_uuid,
                        "experience_title": experience.get("experience_title") or experience.get("title", ""),
                        "skills": []
                    }
                    
                    for skill in top_skills:
                        skill_record = {
                            "skill_uuid": skill.get("UUID"),
                            "skill_model_id": skill.get("modelId"),
                            "preferred_label": skill.get("preferredLabel", ""),
                            "rank": skill[0] if isinstance(skill, tuple) else None  # The rank/index
                        }
                        exp_record["skills"].append(skill_record)
                        
                        # Collect skill IDs for detail lookup
                        if skill.get("UUID") and skill.get("modelId"):
                            skill_ids_to_fetch.add((skill.get("UUID"), skill.get("modelId")))
                    
                    user_record["experiences"].append(exp_record)
            
            # Only add users who have skills
            if user_record["experiences"]:
                user_skills_data.append(user_record)
        
        logger.info(f"Extracted skills from {len(user_skills_data)} users/sessions")
        
        # Get skill collection name from embedding config
        # Default to 'skillsmodelsembeddings' based on the codebase
        skills_collection = taxonomy_db.get_collection("skillsmodelsembeddings")
        
        # Fetch skill details if needed (optional - can be slow for large datasets)
        # Uncomment if you want full skill details
        # logger.info(f"Fetching details for {len(skill_ids_to_fetch)} unique skills...")
        # skill_details = {}
        # for skill_uuid, model_id in skill_ids_to_fetch:
        #     skill_doc = await skills_collection.find_one({
        #         "UUID": skill_uuid,
        #         "modelId": ObjectId(model_id) if model_id else None
        #     })
        #     if skill_doc:
        #         skill_details[skill_uuid] = {
        #             "UUID": skill_doc.get("UUID"),
        #             "preferredLabel": skill_doc.get("preferredLabel"),
        #             "altLabels": skill_doc.get("altLabels", []),
        #             "description": skill_doc.get("description")
        #         }
        
        # Prepare output
        output_data = {
            "export_date": datetime.utcnow().isoformat(),
            "total_users": len(user_skills_data),
            "database": settings.application_database_name,
            "data": user_skills_data
        }
        
        # Write to file
        logger.info(f"Writing output to {output_file}...")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✓ Export complete! Data saved to {output_file}")
        
        # Print summary
        total_experiences = sum(len(user["experiences"]) for user in user_skills_data)
        total_skills = sum(
            len(exp["skills"]) 
            for user in user_skills_data 
            for exp in user["experiences"]
        )
        
        logger.info(f"\nSummary:")
        logger.info(f"  Total users/sessions: {len(user_skills_data)}")
        logger.info(f"  Total experiences: {total_experiences}")
        logger.info(f"  Total skill extractions: {total_skills}")
        
    finally:
        # Close connections
        app_client.close()
        taxonomy_client.close()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Export skills extracted by users from Brujula MongoDB",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="user_skills_export.json",
        help="Output JSON file path (default: user_skills_export.json)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(extract_skills_by_user(args.output))


if __name__ == "__main__":
    main()
