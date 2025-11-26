#!/usr/bin/env python
"""
Configure CORS on CloudCube S3 bucket to allow browser uploads
"""
import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import boto3
from django.conf import settings

def configure_cors():
    """Configure CORS on the CloudCube/S3 bucket"""
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    # CORS configuration
    cors_configuration = {
        'CORSRules': [
            {
                'AllowedHeaders': ['*'],
                'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                'AllowedOrigins': [
                    'https://www.koolclips.ai',
                    'https://koolclips.ai',
                    'https://koolclips-ed69bc2e07f2.herokuapp.com',
                    'http://localhost:8000',
                    'http://127.0.0.1:8000'
                ],
                'ExposeHeaders': ['ETag', 'x-amz-request-id'],
                'MaxAgeSeconds': 3600
            }
        ]
    }
    
    try:
        # Apply CORS configuration
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_configuration
        )
        
        print(f"✅ CORS configuration applied successfully to bucket: {bucket_name}")
        print("\nAllowed origins:")
        for rule in cors_configuration['CORSRules']:
            for origin in rule['AllowedOrigins']:
                print(f"  - {origin}")
        
        # Verify CORS configuration
        response = s3_client.get_bucket_cors(Bucket=bucket_name)
        print(f"\n✅ CORS configuration verified!")
        print(f"   Active CORS rules: {len(response['CORSRules'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error configuring CORS: {str(e)}")
        return False


if __name__ == '__main__':
    print("🔧 Configuring CORS for CloudCube S3 bucket...\n")
    success = configure_cors()
    
    if success:
        print("\n🎉 CORS configuration complete!")
        print("   Browser uploads from koolclips.ai should now work.")
    else:
        print("\n❌ CORS configuration failed!")
        sys.exit(1)
