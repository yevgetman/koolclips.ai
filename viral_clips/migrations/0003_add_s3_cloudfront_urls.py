# Generated migration for S3 and CloudFront URL fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('viral_clips', '0002_add_preprocessing_stage'),
    ]

    operations = [
        migrations.AddField(
            model_name='videojob',
            name='media_file_s3_url',
            field=models.URLField(blank=True, help_text='Direct S3 URL for media file', max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='videojob',
            name='media_file_cloudfront_url',
            field=models.URLField(blank=True, help_text='CloudFront CDN URL for media file', max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='videojob',
            name='extracted_audio_s3_url',
            field=models.URLField(blank=True, help_text='Direct S3 URL for extracted audio', max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='videojob',
            name='extracted_audio_cloudfront_url',
            field=models.URLField(blank=True, help_text='CloudFront CDN URL for extracted audio', max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='clippedvideo',
            name='video_s3_url',
            field=models.URLField(blank=True, help_text='Direct S3 URL for clip', max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='clippedvideo',
            name='video_cloudfront_url',
            field=models.URLField(blank=True, help_text='CloudFront CDN URL for clip', max_length=1000, null=True),
        ),
        migrations.AddField(
            model_name='clippedvideo',
            name='shotstack_render_url',
            field=models.URLField(blank=True, help_text='Shotstack render URL', max_length=1000, null=True),
        ),
    ]
