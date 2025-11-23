#!/usr/bin/env python3
"""
Cloudcube Cleanup Script

This script calls the bulk cleanup API endpoint to clean up old files in Cloudcube.
Can be run manually or scheduled via CRON.

Usage:
    python scripts/cleanup_cloudcube.py --dry-run
    python scripts/cleanup_cloudcube.py --retention-days 7
    python scripts/cleanup_cloudcube.py  # Run actual cleanup with default settings
"""

import argparse
import requests
import sys
import os
from datetime import datetime


def cleanup_cloudcube(api_url, retention_days=5, dry_run=False):
    """
    Call the bulk cleanup API endpoint
    
    Args:
        api_url: Base URL of the API (e.g., http://localhost:8000)
        retention_days: Number of days to retain clips
        dry_run: If True, only simulate cleanup without deleting
    
    Returns:
        dict: Cleanup result
    """
    endpoint = f"{api_url.rstrip('/')}/api/cleanup/bulk/"
    
    payload = {
        'retention_days': retention_days,
        'dry_run': dry_run
    }
    
    print(f"\n{'='*60}")
    print(f"Cloudcube Cleanup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"Endpoint: {endpoint}")
    print(f"Retention Days: {retention_days}")
    print(f"Dry Run: {dry_run}")
    print(f"{'='*60}\n")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=300)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('success'):
            print("✅ Cleanup completed successfully!\n")
            print(f"Message: {result.get('message')}")
            print(f"\nStatistics:")
            print(f"  • Files scanned: {result.get('total_files_scanned')}")
            print(f"  • Files deleted: {result.get('deleted_count')}")
            print(f"  • Space freed: {result.get('deleted_size_mb')} MB")
            print(f"  • Files retained: {result.get('retained_count')}")
            
            if dry_run:
                print(f"\n⚠️  DRY RUN MODE - No files were actually deleted")
                print(f"Run without --dry-run to perform actual cleanup")
            
            # Show sample of deleted files if available
            deleted_files = result.get('deleted_files_sample', [])
            if deleted_files and len(deleted_files) > 0:
                print(f"\nSample of deleted files (first 10):")
                for i, file_key in enumerate(deleted_files[:10], 1):
                    print(f"  {i}. {file_key}")
                if len(deleted_files) > 10:
                    print(f"  ... and {len(deleted_files) - 10} more")
            
            return result
        else:
            print(f"❌ Cleanup failed: {result.get('error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling API: {str(e)}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Clean up old files in Cloudcube storage',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test cleanup without deleting (recommended first step)
  python scripts/cleanup_cloudcube.py --dry-run
  
  # Clean up files older than 7 days
  python scripts/cleanup_cloudcube.py --retention-days 7
  
  # Run actual cleanup with default settings (5 days)
  python scripts/cleanup_cloudcube.py
  
  # Use custom API URL
  python scripts/cleanup_cloudcube.py --api-url https://myapp.herokuapp.com
        """
    )
    
    parser.add_argument(
        '--api-url',
        default=os.getenv('API_URL', 'http://localhost:8000'),
        help='Base URL of the API (default: http://localhost:8000 or API_URL env var)'
    )
    
    parser.add_argument(
        '--retention-days',
        type=int,
        default=5,
        help='Number of days to retain clips (default: 5)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate cleanup without actually deleting files'
    )
    
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Skip confirmation prompt (useful for automated scripts)'
    )
    
    args = parser.parse_args()
    
    # Confirmation prompt (unless dry-run or --confirm flag)
    if not args.dry_run and not args.confirm:
        print("\n⚠️  WARNING: This will permanently delete files from Cloudcube!")
        print(f"Clips older than {args.retention_days} days will be deleted.")
        print("\nIt's recommended to run with --dry-run first to preview the cleanup.")
        
        response = input("\nDo you want to proceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Cleanup cancelled.")
            sys.exit(0)
    
    # Run cleanup
    result = cleanup_cloudcube(
        api_url=args.api_url,
        retention_days=args.retention_days,
        dry_run=args.dry_run
    )
    
    # Exit with appropriate status code
    if result and result.get('success'):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
