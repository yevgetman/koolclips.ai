from rest_framework import serializers
from .models import VideoJob, TranscriptSegment, ClippedVideo
from .utils import validate_media_file


class ClippedVideoSerializer(serializers.ModelSerializer):
    """Serializer for ClippedVideo model"""
    
    # Return CloudFront URL if available, otherwise video_url
    public_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ClippedVideo
        fields = [
            'id', 'status', 'video_url', 'video_file', 'public_url',
            'video_cloudfront_url', 'video_s3_url',
            'error_message', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    
    def get_public_url(self, obj):
        """Return the best available public URL for the clip"""
        return obj.get_video_cloudfront_url() or obj.video_url


class TranscriptSegmentSerializer(serializers.ModelSerializer):
    """Serializer for TranscriptSegment model"""
    
    clip = ClippedVideoSerializer(read_only=True)
    
    class Meta:
        model = TranscriptSegment
        fields = [
            'id', 'title', 'description', 'reasoning',
            'start_time', 'end_time', 'duration', 'segment_order',
            'clip', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class VideoJobSerializer(serializers.ModelSerializer):
    """Serializer for VideoJob model"""
    
    segments = TranscriptSegmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = VideoJob
        fields = [
            'id', 'media_file', 'file_type', 'status', 'error_message',
            'num_segments', 'min_duration', 'max_duration',
            'extracted_audio_path', 'transcript_json', 'segments',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'file_type', 'status', 'error_message', 'extracted_audio_path',
                           'transcript_json', 'created_at', 'updated_at', 'completed_at', 'segments']


class VideoJobCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a VideoJob"""
    
    class Meta:
        model = VideoJob
        fields = ['media_file', 'num_segments', 'min_duration', 'max_duration']
    
    def validate_media_file(self, value):
        """Validate the uploaded media file"""
        is_valid, file_type, error_message = validate_media_file(value)
        
        if not is_valid:
            raise serializers.ValidationError(error_message)
        
        # Store file type for later use
        self.context['file_type'] = file_type
        return value
        
    def create(self, validated_data):
        # Add file type from validation
        validated_data['file_type'] = self.context.get('file_type', 'video')
        
        # Create the job
        job = VideoJob.objects.create(**validated_data)
        
        # Store S3/CloudFront URLs if file was uploaded to S3
        if job.media_file and hasattr(job.media_file, 'url'):
            from .services.s3_service import S3Service
            if S3Service.is_s3_configured():
                from django.conf import settings
                
                # Get actual S3 key (includes cube prefix for Cloudcube)
                if hasattr(job.media_file, 'storage'):
                    s3_key = job.media_file.storage._normalize_name(job.media_file.name)
                else:
                    s3_key = job.media_file.name
                
                # Generate S3 URL with proper cube prefix
                bucket = settings.AWS_STORAGE_BUCKET_NAME
                region = settings.AWS_S3_REGION_NAME
                job.media_file_s3_url = f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
                
                # For Cloudcube, also set as cloudfront URL (since we don't have CloudFront)
                # For standalone AWS, use CloudFront domain if configured
                if settings.AWS_CLOUDFRONT_DOMAIN_INPUT:
                    job.media_file_cloudfront_url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN_INPUT}/{s3_key}"
                else:
                    # No CloudFront, use S3 URL directly (for Cloudcube)
                    job.media_file_cloudfront_url = job.media_file_s3_url
                
                job.save()
        
        # Trigger the processing pipeline
        from .tasks import process_video_job
        process_video_job.delay(str(job.id))
        
        return job


class VideoJobListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing VideoJobs"""
    
    segments_count = serializers.SerializerMethodField()
    completed_clips_count = serializers.SerializerMethodField()
    
    class Meta:
        model = VideoJob
        fields = [
            'id', 'file_type', 'status', 'num_segments', 'segments_count', 
            'completed_clips_count', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_segments_count(self, obj):
        return obj.segments.count()
    
    def get_completed_clips_count(self, obj):
        return obj.segments.filter(clip__status='completed').count()
