"""
Database package for the AI-Driven Personalized VR Teaching System.
Contains Supabase and Pinecone client implementations.
"""

from db.supabase_client import SupabaseManager, supabase_manager

__all__ = [
    "SupabaseManager",
    "supabase_manager",
]
