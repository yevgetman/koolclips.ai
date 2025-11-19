from django.contrib import admin
from .models import VideoJob, TranscriptSegment, ClippedVideo


class TranscriptSegmentInline(admin.TabularInline):
    model = TranscriptSegment
    extra = 0
    readonly_fields = ('created_at',)


class ClippedVideoInline(admin.StackedInline):
    model = ClippedVideo
    extra = 0
    readonly_fields = ('created_at', 'updated_at', 'completed_at')


@admin.register(VideoJob)
class VideoJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'num_segments', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('id',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'completed_at')
    inlines = [TranscriptSegmentInline]
    
    fieldsets = (
        ('Job Information', {
            'fields': ('id', 'video_file', 'status', 'error_message')
        }),
        ('Configuration', {
            'fields': ('num_segments', 'min_duration', 'max_duration')
        }),
        ('Transcript Data', {
            'fields': ('transcript_json',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )


@admin.register(TranscriptSegment)
class TranscriptSegmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'video_job', 'start_time', 'end_time', 'duration', 'segment_order')
    list_filter = ('created_at',)
    search_fields = ('title', 'description')
    readonly_fields = ('id', 'created_at')
    inlines = [ClippedVideoInline]


@admin.register(ClippedVideo)
class ClippedVideoAdmin(admin.ModelAdmin):
    list_display = ('segment', 'status', 'shotstack_render_id', 'created_at')
    list_filter = ('status', 'created_at')
    readonly_fields = ('id', 'created_at', 'updated_at', 'completed_at')
