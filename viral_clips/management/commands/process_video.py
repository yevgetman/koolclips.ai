from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
import os
import time
from viral_clips.models import VideoJob
from viral_clips.utils import detect_file_type


class Command(BaseCommand):
    help = 'Process a video or audio file to create viral clips'
    
    def add_arguments(self, parser):
        parser.add_argument('media_path', type=str, help='Path to the video or audio file')
        parser.add_argument(
            '--segments',
            type=int,
            default=5,
            help='Number of segments to generate (default: 5)'
        )
        parser.add_argument(
            '--min-duration',
            type=int,
            default=60,
            help='Minimum segment duration in seconds (default: 60)'
        )
        parser.add_argument(
            '--max-duration',
            type=int,
            default=180,
            help='Maximum segment duration in seconds (default: 180)'
        )
        parser.add_argument(
            '--wait',
            action='store_true',
            help='Wait for processing to complete and show status'
        )
    
    def handle(self, *args, **options):
        media_path = options['media_path']
        
        # Validate media file exists
        if not os.path.exists(media_path):
            raise CommandError(f'Media file not found: {media_path}')
        
        # Detect file type
        file_type = detect_file_type(media_path)
        if file_type == 'unknown':
            raise CommandError('Unsupported file type. Please provide a video or audio file.')
        
        self.stdout.write(self.style.SUCCESS(f'Processing {file_type} file: {media_path}'))
        
        # Create VideoJob
        with open(media_path, 'rb') as f:
            media_file = File(f, name=os.path.basename(media_path))
            job = VideoJob.objects.create(
                media_file=media_file,
                file_type=file_type,
                num_segments=options['segments'],
                min_duration=options['min_duration'],
                max_duration=options['max_duration']
            )
        
        self.stdout.write(self.style.SUCCESS(f'Created job: {job.id}'))
        
        # Trigger processing
        from viral_clips.tasks import process_video_job
        process_video_job.delay(str(job.id))
        
        self.stdout.write(self.style.SUCCESS('Processing started...'))
        
        if options['wait']:
            self.wait_for_completion(job)
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'\nJob submitted! Check status with:\n'
                    f'python manage.py check_job {job.id}'
                )
            )
    
    def wait_for_completion(self, job):
        """Wait for job to complete and show progress"""
        self.stdout.write('\nWaiting for processing to complete...')
        
        last_status = None
        while True:
            job.refresh_from_db()
            
            if job.status != last_status:
                self.stdout.write(f'Status: {job.status}')
                last_status = job.status
            
            if job.status == 'completed':
                self.stdout.write(self.style.SUCCESS('\n✓ Processing completed!'))
                self.show_results(job)
                break
            elif job.status == 'failed':
                self.stdout.write(self.style.ERROR(f'\n✗ Processing failed: {job.error_message}'))
                break
            
            time.sleep(2)
    
    def show_results(self, job):
        """Show results of processing"""
        segments = job.segments.all()
        
        self.stdout.write(f'\nFound {segments.count()} viral segments:')
        
        for i, segment in enumerate(segments, 1):
            self.stdout.write(f'\n{i}. {segment.title}')
            self.stdout.write(f'   Time: {segment.start_time:.1f}s - {segment.end_time:.1f}s')
            self.stdout.write(f'   Duration: {segment.duration:.1f}s')
            
            if hasattr(segment, 'clip'):
                clip = segment.clip
                if clip.status == 'completed':
                    self.stdout.write(self.style.SUCCESS(f'   Clip: {clip.video_url}'))
                else:
                    self.stdout.write(f'   Clip status: {clip.status}')
