#!/usr/bin/env python
"""
Script to clean up orphaned Profile records.
Run this when you get IntegrityError for duplicate user_id in profiles.

Usage:
    docker exec -it nole-app python cleanup_orphaned_profiles.py
"""
import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nole.settings')
django.setup()

from accounts.models import Profile, CustomUser

def cleanup_orphaned_profiles():
    """Delete profiles that don't have a corresponding user."""
    print("Checking for orphaned profiles...")
    
    # Get all user IDs that exist
    existing_user_ids = set(CustomUser.objects.values_list('id', flat=True))
    
    # Get all profile user_ids
    all_profile_user_ids = set(Profile.objects.values_list('user_id', flat=True))
    
    # Find orphaned profile user_ids (profiles without users)
    orphaned_user_ids = all_profile_user_ids - existing_user_ids
    
    if not orphaned_user_ids:
        print("✓ No orphaned profiles found. Database is clean!")
        return
    
    print(f"Found {len(orphaned_user_ids)} orphaned profile(s) for user IDs: {sorted(orphaned_user_ids)}")
    
    # Delete orphaned profiles
    orphaned_profiles = Profile.objects.filter(user_id__in=orphaned_user_ids)
    deleted_count, _ = orphaned_profiles.delete()
    
    print(f"✓ Successfully deleted {deleted_count} orphaned profile(s)!")
    print("You can now add new users without IntegrityError.")

if __name__ == '__main__':
    cleanup_orphaned_profiles()
