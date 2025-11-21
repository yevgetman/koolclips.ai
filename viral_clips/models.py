from django.db import models
from django.utils import timezone
import uuid


class VideoJob(models.Model):
    """Model to track video/audio processing jobs"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('preprocessing', 'Preprocessing'),
        ('transcribing', 'Transcribing'),
        ('analyzing', 'Analyzing'),
        ('clipping', 'Clipping'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    FILE_TYPE_CHOICES = [
        ('video', 'Video'),
        ('audio', 'Audio'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    media_file = models.FileField(upload_to='uploads/media/', help_text='Video or audio file')
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='video')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    
    # Preprocessing data
    extracted_audio_path = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text='Path to extracted audio file (for video uploads)'
    )
    
    # S3/CloudFront URLs
    media_file_s3_url = models.URLField(max_length=1000, blank=True, null=True, help_text='Direct S3 URL for media file')
    media_file_cloudfront_url = models.URLField(max_length=1000, blank=True, null=True, help_text='CloudFront CDN URL for media file')
    extracted_audio_s3_url = models.URLField(max_length=1000, blank=True, null=True, help_text='Direct S3 URL for extracted audio')
    extracted_audio_cloudfront_url = models.URLField(max_length=1000, blank=True, null=True, help_text='CloudFront CDN URL for extracted audio')
    
    # Transcript data
    transcript_json = models.JSONField(blank=True, null=True)
    
    # Configuration
    num_segments = models.IntegerField(default=3)
    min_duration = models.IntegerField(default=60, help_text='(Deprecated) Minimum segment duration in seconds - LLM now decides length based on content')
    max_duration = models.IntegerField(default=300, help_text='Maximum segment duration in seconds (hard limit: 5 minutes)')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.file_type.capitalize()} Job {self.id} - {self.status}"
    
    def is_audio_only(self):
        """Check if this job is for audio-only processing"""
        return self.file_type == 'audio'
    
    def get_media_cloudfront_url(self):
        """Get CloudFront URL for media file"""
        if self.media_file_cloudfront_url:
            return self.media_file_cloudfront_url
        
        if self.media_file:
            from django.conf import settings
            if settings.AWS_CLOUDFRONT_DOMAIN_INPUT:
                return f"https://{settings.AWS_CLOUDFRONT_DOMAIN_INPUT}/{self.media_file.name}"
        
        return None
    
    def get_audio_cloudfront_url(self):
        """Get CloudFront URL for extracted audio"""
        if self.extracted_audio_cloudfront_url:
            return self.extracted_audio_cloudfront_url
        
        return None


class TranscriptSegment(models.Model):
    """Model to store identified viral segments"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    video_job = models.ForeignKey(VideoJob, on_delete=models.CASCADE, related_name='segments')
    
    # Segment metadata
    title = models.CharField(max_length=255)
    description = models.TextField()
    reasoning = models.TextField(help_text='Why this segment is viral/provocative')
    
    # Timing information
    start_time = models.FloatField(help_text='Start time in seconds')
    end_time = models.FloatField(help_text='End time in seconds')
    duration = models.FloatField(help_text='Duration in seconds')
    
    # Ordering
    segment_order = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['video_job', 'segment_order']
    
    def __str__(self):
        return f"{self.title} ({self.start_time}s - {self.end_time}s)"


class ClippedVideo(models.Model):
    """Model to store clipped video files"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    segment = models.OneToOneField(TranscriptSegment, on_delete=models.CASCADE, related_name='clip')
    
    # Shotstack data
    shotstack_render_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Output file
    video_url = models.URLField(blank=True, null=True)
    video_file = models.FileField(upload_to='clips/', blank=True, null=True)
    
    # S3/CloudFront URLs
    video_s3_url = models.URLField(max_length=1000, blank=True, null=True, help_text='Direct S3 URL for clip')
    video_cloudfront_url = models.URLField(max_length=1000, blank=True, null=True, help_text='CloudFront CDN URL for clip')
    shotstack_render_url = models.URLField(max_length=1000, blank=True, null=True, help_text='Shotstack render URL')
    
    # Metadata
    error_message = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Clip for {self.segment.title} - {self.status}"
    
    def get_video_cloudfront_url(self):
        """Get CloudFront URL for video clip"""
        if self.video_cloudfront_url:
            return self.video_cloudfront_url
        
        if self.video_file:
            from django.conf import settings
            if settings.AWS_CLOUDFRONT_DOMAIN_OUTPUT:
                return f"https://{settings.AWS_CLOUDFRONT_DOMAIN_OUTPUT}/{self.video_file.name}"
        
        return None
