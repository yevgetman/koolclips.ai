"""
TUS Protocol Views for Resumable Uploads

TUS (https://tus.io/) is an open protocol for resumable uploads.
This module implements TUS endpoints that receive uploads and then
transfer completed files to S3.
"""

import os
import uuid
import logging
import hashlib
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from .services.s3_service import S3Service

logger = logging.getLogger(__name__)

# TUS Protocol Version
TUS_VERSION = '1.0.0'
TUS_SUPPORTED_VERSIONS = ['1.0.0']
TUS_EXTENSIONS = ['creation', 'creation-with-upload', 'termination', 'checksum']
TUS_MAX_SIZE = getattr(settings, 'TUS_MAX_SIZE', 5 * 1024 * 1024 * 1024)  # 5GB

# Directory to store incomplete uploads
TUS_UPLOAD_DIR = getattr(settings, 'TUS_UPLOAD_DIR', os.path.join(settings.BASE_DIR, 'tus-uploads'))

# In-memory store for upload metadata (use Redis/DB in production)
_upload_metadata = {}


def ensure_upload_dir():
    """Ensure the TUS upload directory exists"""
    Path(TUS_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


def get_upload_path(upload_id):
    """Get the file path for an upload"""
    return os.path.join(TUS_UPLOAD_DIR, upload_id)


def get_upload_info_path(upload_id):
    """Get the info file path for an upload"""
    return os.path.join(TUS_UPLOAD_DIR, f"{upload_id}.info")


def parse_metadata(metadata_header):
    """Parse TUS Upload-Metadata header"""
    if not metadata_header:
        return {}
    
    metadata = {}
    for item in metadata_header.split(','):
        item = item.strip()
        if ' ' in item:
            key, value = item.split(' ', 1)
            # Value is base64 encoded
            import base64
            try:
                metadata[key] = base64.b64decode(value).decode('utf-8')
            except Exception:
                metadata[key] = value
        else:
            metadata[item] = ''
    
    return metadata


def add_tus_headers(response, upload_id=None, offset=None):
    """Add standard TUS headers to response"""
    response['Tus-Resumable'] = TUS_VERSION
    response['Tus-Version'] = ','.join(TUS_SUPPORTED_VERSIONS)
    response['Tus-Extension'] = ','.join(TUS_EXTENSIONS)
    response['Tus-Max-Size'] = str(TUS_MAX_SIZE)
    
    if upload_id:
        response['Upload-Offset'] = str(offset or 0)
    
    # CORS headers
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, DELETE, HEAD, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Upload-Length, Upload-Metadata, Upload-Offset, Tus-Resumable, Upload-Concat, Upload-Defer-Length'
    response['Access-Control-Expose-Headers'] = 'Upload-Offset, Location, Upload-Length, Tus-Version, Tus-Resumable, Tus-Max-Size, Tus-Extension, Upload-Metadata'
    
    return response


@csrf_exempt
def tus_options(request):
    """Handle OPTIONS request for TUS capability discovery"""
    response = HttpResponse(status=204)
    return add_tus_headers(response)


@csrf_exempt
def tus_create(request):
    """
    Handle POST request to create a new upload
    
    TUS Creation Extension:
    - Client sends POST with Upload-Length header
    - Server responds with Location header containing upload URL
    """
    ensure_upload_dir()
    
    # Check TUS version
    tus_version = request.headers.get('Tus-Resumable')
    if tus_version not in TUS_SUPPORTED_VERSIONS:
        response = HttpResponse(status=412)  # Precondition Failed
        return add_tus_headers(response)
    
    # Get upload length
    upload_length = request.headers.get('Upload-Length')
    if not upload_length:
        # Check for Upload-Defer-Length
        defer_length = request.headers.get('Upload-Defer-Length')
        if defer_length != '1':
            return HttpResponse('Upload-Length header required', status=400)
        upload_length = None
    else:
        upload_length = int(upload_length)
        
        # Check max size
        if upload_length > TUS_MAX_SIZE:
            response = HttpResponse(status=413)  # Request Entity Too Large
            return add_tus_headers(response)
    
    # Parse metadata
    metadata = parse_metadata(request.headers.get('Upload-Metadata', ''))
    
    # Generate upload ID
    upload_id = str(uuid.uuid4())
    
    # Store upload info
    upload_info = {
        'id': upload_id,
        'length': upload_length,
        'offset': 0,
        'metadata': metadata,
        'filename': metadata.get('filename', 'unknown'),
        'filetype': metadata.get('filetype', 'application/octet-stream'),
    }
    _upload_metadata[upload_id] = upload_info
    
    # Save info to file for persistence
    import json
    with open(get_upload_info_path(upload_id), 'w') as f:
        json.dump(upload_info, f)
    
    # Create empty file
    with open(get_upload_path(upload_id), 'wb') as f:
        pass
    
    logger.info(f"TUS: Created upload {upload_id} for {upload_info['filename']} ({upload_length} bytes)")
    
    # Build location URL
    location = request.build_absolute_uri(f'/api/tus/{upload_id}')
    
    # Handle creation-with-upload extension (data in POST body)
    if request.body:
        content_type = request.headers.get('Content-Type', '')
        if content_type == 'application/offset+octet-stream':
            # Write the body data
            with open(get_upload_path(upload_id), 'ab') as f:
                f.write(request.body)
            upload_info['offset'] = len(request.body)
            _upload_metadata[upload_id] = upload_info
            
            # Update info file
            with open(get_upload_info_path(upload_id), 'w') as f:
                json.dump(upload_info, f)
    
    response = HttpResponse(status=201)
    response['Location'] = location
    return add_tus_headers(response, upload_id, upload_info['offset'])


@csrf_exempt
def tus_upload(request, upload_id):
    """
    Handle HEAD, PATCH, DELETE requests for an upload
    
    - HEAD: Get current offset
    - PATCH: Append data to upload
    - DELETE: Cancel upload (Termination extension)
    """
    import json
    
    # Check TUS version
    tus_version = request.headers.get('Tus-Resumable')
    if tus_version and tus_version not in TUS_SUPPORTED_VERSIONS:
        response = HttpResponse(status=412)
        return add_tus_headers(response)
    
    # Load upload info
    info_path = get_upload_info_path(upload_id)
    upload_path = get_upload_path(upload_id)
    
    if not os.path.exists(info_path):
        # Check in-memory
        if upload_id not in _upload_metadata:
            return HttpResponse('Upload not found', status=404)
        upload_info = _upload_metadata[upload_id]
    else:
        with open(info_path, 'r') as f:
            upload_info = json.load(f)
        _upload_metadata[upload_id] = upload_info
    
    if request.method == 'OPTIONS':
        response = HttpResponse(status=204)
        return add_tus_headers(response)
    
    elif request.method == 'HEAD':
        # Return current offset
        response = HttpResponse(status=200)
        response['Upload-Offset'] = str(upload_info['offset'])
        response['Upload-Length'] = str(upload_info['length']) if upload_info['length'] else ''
        response['Cache-Control'] = 'no-store'
        return add_tus_headers(response, upload_id, upload_info['offset'])
    
    elif request.method == 'PATCH':
        # Append data to upload
        content_type = request.headers.get('Content-Type', '')
        if content_type != 'application/offset+octet-stream':
            return HttpResponse('Invalid Content-Type', status=415)
        
        # Check offset
        client_offset = int(request.headers.get('Upload-Offset', 0))
        if client_offset != upload_info['offset']:
            response = HttpResponse(status=409)  # Conflict
            return add_tus_headers(response, upload_id, upload_info['offset'])
        
        # Append data
        data = request.body
        with open(upload_path, 'ab') as f:
            f.write(data)
        
        new_offset = upload_info['offset'] + len(data)
        upload_info['offset'] = new_offset
        _upload_metadata[upload_id] = upload_info
        
        # Update info file
        with open(info_path, 'w') as f:
            json.dump(upload_info, f)
        
        logger.info(f"TUS: Upload {upload_id} progress: {new_offset}/{upload_info['length']} bytes")
        
        # Check if upload is complete
        if upload_info['length'] and new_offset >= upload_info['length']:
            logger.info(f"TUS: Upload {upload_id} complete, transferring to S3...")
            
            # Transfer to S3
            try:
                transfer_to_s3(upload_id, upload_info)
            except Exception as e:
                logger.error(f"TUS: Failed to transfer {upload_id} to S3: {e}")
                # Don't fail the upload response, S3 transfer can be retried
        
        response = HttpResponse(status=204)
        return add_tus_headers(response, upload_id, new_offset)
    
    elif request.method == 'DELETE':
        # Cancel upload (Termination extension)
        try:
            if os.path.exists(upload_path):
                os.remove(upload_path)
            if os.path.exists(info_path):
                os.remove(info_path)
            if upload_id in _upload_metadata:
                del _upload_metadata[upload_id]
            logger.info(f"TUS: Deleted upload {upload_id}")
        except Exception as e:
            logger.error(f"TUS: Failed to delete upload {upload_id}: {e}")
        
        return HttpResponse(status=204)
    
    return HttpResponse(status=405)


def transfer_to_s3(upload_id, upload_info):
    """Transfer completed upload to S3"""
    upload_path = get_upload_path(upload_id)
    
    if not os.path.exists(upload_path):
        raise FileNotFoundError(f"Upload file not found: {upload_path}")
    
    # Generate S3 key
    filename = upload_info.get('filename', 'unknown')
    s3_key = f"uploads/tus/{upload_id}/{filename}"
    
    # Upload to S3
    s3_service = S3Service()
    
    with open(upload_path, 'rb') as f:
        # For large files, use multipart upload
        file_size = os.path.getsize(upload_path)
        
        if file_size > 100 * 1024 * 1024:  # > 100MB
            # Use multipart upload
            logger.info(f"TUS: Using multipart upload for {upload_id} ({file_size} bytes)")
            
            # Initiate multipart upload
            content_type = upload_info.get('filetype', 'application/octet-stream')
            multipart = s3_service.initiate_multipart_upload(s3_key, content_type=content_type)
            
            part_size = 100 * 1024 * 1024  # 100MB parts
            parts = []
            part_number = 1
            
            while True:
                data = f.read(part_size)
                if not data:
                    break
                
                # Upload part
                response = s3_service.s3_client.upload_part(
                    Bucket=s3_service.input_bucket,
                    Key=s3_key,
                    PartNumber=part_number,
                    UploadId=multipart['upload_id'],
                    Body=data
                )
                
                parts.append({
                    'PartNumber': part_number,
                    'ETag': response['ETag']
                })
                part_number += 1
            
            # Complete multipart upload
            s3_service.complete_multipart_upload(s3_key, multipart['upload_id'], parts)
        else:
            # Simple upload
            s3_service.s3_client.put_object(
                Bucket=s3_service.input_bucket,
                Key=s3_key,
                Body=f,
                ContentType=upload_info.get('filetype', 'application/octet-stream')
            )
    
    # Get public URL
    public_url = s3_service.get_public_url_from_key(s3_key)
    
    # Update metadata with S3 info
    upload_info['s3_key'] = s3_key
    upload_info['s3_url'] = public_url
    upload_info['completed'] = True
    _upload_metadata[upload_id] = upload_info
    
    # Update info file
    import json
    with open(get_upload_info_path(upload_id), 'w') as f:
        json.dump(upload_info, f)
    
    logger.info(f"TUS: Transferred {upload_id} to S3: {s3_key}")
    
    # Clean up local file (keep info for reference)
    try:
        os.remove(upload_path)
    except Exception:
        pass
    
    return public_url


@csrf_exempt
def tus_endpoint(request, upload_id=None):
    """
    Main TUS endpoint router
    
    Routes:
    - OPTIONS /api/tus/ - Capability discovery
    - POST /api/tus/ - Create new upload
    - HEAD /api/tus/{id} - Get upload status
    - PATCH /api/tus/{id} - Append data
    - DELETE /api/tus/{id} - Cancel upload
    """
    if request.method == 'OPTIONS':
        return tus_options(request)
    
    if upload_id:
        return tus_upload(request, upload_id)
    else:
        if request.method == 'POST':
            return tus_create(request)
        return HttpResponse(status=405)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tus_upload_info(request, upload_id):
    """
    Get upload info and S3 URL for a completed upload
    
    GET /api/tus/{id}/info
    
    Returns JSON with upload metadata and S3 URL if complete
    """
    import json
    
    info_path = get_upload_info_path(upload_id)
    
    if upload_id in _upload_metadata:
        upload_info = _upload_metadata[upload_id]
    elif os.path.exists(info_path):
        with open(info_path, 'r') as f:
            upload_info = json.load(f)
    else:
        return JsonResponse({'error': 'Upload not found'}, status=404)
    
    return JsonResponse({
        'id': upload_id,
        'filename': upload_info.get('filename'),
        'filetype': upload_info.get('filetype'),
        'length': upload_info.get('length'),
        'offset': upload_info.get('offset'),
        'completed': upload_info.get('completed', False),
        's3_key': upload_info.get('s3_key'),
        's3_url': upload_info.get('s3_url'),
    })
