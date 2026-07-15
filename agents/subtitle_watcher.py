#!/usr/bin/env python3
"""
Agent 1: Content Watcher (Lightweight Version)
Extracts subtitles directly from YouTube - NO video/audio download.
Background process, minimal storage usage.
"""

import os
import json
import subprocess
import psycopg2
import logging
from typing import Optional, Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('Watcher')


class SubtitleWatcher:
    """
    Lightweight content watcher - subtitles only, no downloads.
    
    Features:
    - Extracts subtitles directly (no video download)
    - Background process (silent)
    - Minimal storage usage
    - Works with YouTube auto-generated subtitles
    """
    
    def __init__(self, config: Dict):
        self.groq_api_key = config.get('groq_api_key')
        self.postgres_config = {
            'host': config.get('postgres_host', 'localhost'),
            'port': config.get('postgres_port', '5432'),
            'dbname': config.get('postgres_db', 'certificate_tracker'),
            'user': config.get('postgres_user', 'postgres'),
            'password': config.get('postgres_password', 'postgres')
        }
        logger.info("SubtitleWatcher initialized (no download mode)")
    
    def get_db(self):
        return psycopg2.connect(**self.postgres_config)
    
    def extract_subtitles(self, url: str) -> List[Dict]:
        """
        Extract subtitles from YouTube video/playlist.
        NO video download - just subtitle extraction.
        """
        logger.info(f"Extracting subtitles from: {url}")
        
        # Get playlist info
        cmd = ['yt-dlp', '--flat-playlist', '--dump-json', url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    video = json.loads(line)
                    videos.append({
                        'id': video.get('id'),
                        'title': video.get('title', 'Unknown'),
                        'url': video.get('url', f"https://youtube.com/watch?v={video.get('id')}")
                    })
                except:
                    pass
        
        if not videos:
            # Single video
            cmd = ['yt-dlp', '--dump-json', url]
            result = subprocess.run(cmd, capture_output=True, text=True)
            video = json.loads(result.stdout)
            videos = [{
                'id': video.get('id'),
                'title': video.get('title', 'Unknown'),
                'url': url
            }]
        
        logger.info(f"Found {len(videos)} videos")
        return videos
    
    def get_subtitles_only(self, video_id: str) -> Optional[str]:
        """
        Get subtitles WITHOUT downloading video.
        Uses yt-dlp --write-sub --skip-download
        """
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write subtitles only, skip video download
            cmd = [
                'yt-dlp',
                '--write-sub',
                '--write-auto-sub',
                '--sub-lang', 'en',
                '--skip-download',  # KEY: Don't download video!
                '--sub-format', 'vtt',
                '-o', f'{tmpdir}/%(id)s',
                f'https://www.youtube.com/watch?v={video_id}'
            ]
            
            subprocess.run(cmd, capture_output=True, text=True)
            
            # Check for subtitle file
            sub_file = f"{tmpdir}/{video_id}.en.vtt"
            if os.path.exists(sub_file):
                with open(sub_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return self.parse_vtt(content)
            
            return None
    
    def parse_vtt(self, vtt: str) -> str:
        """Parse VTT to plain text."""
        import re
        lines = []
        for line in vtt.split('\n'):
            if '-->' in line or line.strip() == '' or line.startswith('WEBVTT'):
                continue
            clean = re.sub(r'<[^>]+>', '', line).strip()
            if clean and clean not in lines[-1:]:
                lines.append(clean)
        return ' '.join(lines)
    
    def store_transcript(self, course_name: str, title: str, 
                        transcript: str, video_url: str):
        """Store transcript in database."""
        conn = self.get_db()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO workshop_transcripts 
                (course_name, chapter_title, transcript, video_url, word_count)
                VALUES (%s, %s, %s, %s, %s)
            """, (course_name, title, transcript, video_url, len(transcript.split())))
            conn.commit()
        finally:
            cur.close()
            conn.close()
    
    def process(self, url: str, course_name: str = None, provider: str = 'YouTube'):
        """
        Main processing - extract subtitles and store.
        Background process, no user interaction needed.
        """
        start = datetime.now()
        
        # Get videos
        videos = self.extract_subtitles(url)
        
        if not course_name:
            course_name = videos[0]['title'] if len(videos) == 1 else f"Course {datetime.now().strftime('%Y%m%d')}"
        
        # Update progress
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO course_progress (course_name, provider, status, videos_total)
            VALUES (%s, %s, 'processing', %s)
            ON CONFLICT (course_name) DO UPDATE SET status = 'processing'
        """, (course_name, provider, len(videos)))
        conn.commit()
        cur.close()
        conn.close()
        
        # Process each video
        processed = 0
        total_words = 0
        
        for i, video in enumerate(videos, 1):
            try:
                # Get subtitles (no download!)
                subtitles = self.get_subtitles_only(video['id'])
                
                if subtitles:
                    self.store_transcript(course_name, video['title'], subtitles, video['url'])
                    processed += 1
                    total_words += len(subtitles.split())
                    logger.info(f"[{i}/{len(videos)}] ✓ {video['title'][:50]}")
                else:
                    logger.warning(f"[{i}/{len(videos)}] ✗ No subtitles: {video['title'][:50]}")
                    
            except Exception as e:
                logger.error(f"[{i}/{len(videos)}] Error: {e}")
        
        # Update final status
        duration = (datetime.now() - start).total_seconds()
        
        conn = self.get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE course_progress 
            SET status = 'transcribed', videos_completed = %s, 
                hours_completed = %s, updated_at = CURRENT_TIMESTAMP
            WHERE course_name = %s
        """, (processed, total_words / 15000, course_name))  # ~15000 words per hour
        conn.commit()
        cur.close()
        conn.close()
        
        result = {
            'course': course_name,
            'videos': processed,
            'words': total_words,
            'time': f"{duration:.1f}s",
            'storage': '0 MB (subtitles only)'
        }
        
        logger.info(f"✅ Done: {processed}/{len(videos)} videos, {total_words} words, {duration:.1f}s")
        return result


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Subtitle-only content watcher')
    parser.add_argument('url', help='YouTube URL')
    parser.add_argument('--name', help='Course name')
    parser.add_argument('--provider', default='YouTube')
    parser.add_argument('--postgres-host', default='localhost')
    parser.add_argument('--postgres-port', default='5432')
    parser.add_argument('--postgres-db', default='certificate_tracker')
    parser.add_argument('--postgres-user', default='postgres')
    parser.add_argument('--postgres-password', default='postgres')
    
    args = parser.parse_args()
    
    config = {
        'postgres_host': args.postgres_host,
        'postgres_port': args.postgres_port,
        'postgres_db': args.postgres_db,
        'postgres_user': args.postgres_user,
        'postgres_password': args.postgres_password
    }
    
    watcher = SubtitleWatcher(config)
    result = watcher.process(args.url, args.name, args.provider)
    print(json.dumps(result, indent=2))
