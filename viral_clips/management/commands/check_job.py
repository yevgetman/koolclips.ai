from django.core.management.base import BaseCommand, CommandError
from viral_clips.models import VideoJob


class Command(BaseCommand):
    help = 'Check the status of a video processing job'
    
    def add_arguments(self, parser):
        parser.add_argument('job_id', type=str, help='ID of the video job')
    
    def handle(self, *args, **options):
        job_id = options['job_id']
        
        try:
            job = VideoJob.objects.get(id=job_id)
        except VideoJob.DoesNotExist:
            raise CommandError(f'Job not found: {job_id}')
        
        # Show job status
        self.stdout.write(self.style.SUCCESS(f'Job ID: {job.id}'))
        self.stdout.write(f'Status: {job.status}')
        self.stdout.write(f'Created: {job.created_at}')
        
        if job.error_message:
            self.stdout.write(self.style.ERROR(f'Error: {job.error_message}'))
        
        # Show segments
        segments = job.segments.all()
        if segments.exists():
            self.stdout.write(f'\nSegments ({segments.count()}):')
            
            for i, segment in enumerate(segments, 1):
                self.stdout.write(f'\n{i}. {segment.title}')
                self.stdout.write(f'   {segment.start_time:.1f}s - {segment.end_time:.1f}s ({segment.duration:.1f}s)')
                self.stdout.write(f'   {segment.description}')
                
                if hasattr(segment, 'clip'):
                    clip = segment.clip
                    self.stdout.write(f'   Clip status: {clip.status}')
                    
                    if clip.status == 'completed' and clip.video_url:
                        self.stdout.write(self.style.SUCCESS(f'   URL: {clip.video_url}'))
                    elif clip.error_message:
                        self.stdout.write(self.style.ERROR(f'   Error: {clip.error_message}'))
        else:
            self.stdout.write('\nNo segments found yet.')
        
        # Show summary
        if job.status == 'completed':
            completed_clips = segments.filter(clip__status='completed').count()
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Job completed! {completed_clips}/{segments.count()} clips ready.'
                )
            )
