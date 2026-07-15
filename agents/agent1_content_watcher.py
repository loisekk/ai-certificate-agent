#!/usr/bin/env python3
"""
Agent 1: Content Watcher
Downloads workshop videos and transcribes them using Groq Whisper API.
Stores transcripts in PostgreSQL for Agent 2 to process.
"""

import os
import json
import subprocess
import requests
import psycopg2
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ContentWatcher')


class ContentWatcher:
    """
    Agent 1: Downloads and transcribes workshop videos.
    
    Pipeline:
    1. Fetch course metadata (yt-dlp)
    2. Download video/audio (yt-dlp)
    3. Check for existing subtitles
    4. Transcribe audio (Groq Whisper API)
    5. Store transcripts in PostgreSQL
    """
    
    def __init__(self, config: Dict):
        """
        Initialize ContentWatcher with configuration.
        
        Args:
            config: Dictionary containing:
                - groq_api_key: Groq API key
                - postgres_host: PostgreSQL host
                - postgres_port: PostgreSQL port
                - postgres_db: Database name
                - postgres_user: Database user
                - postgres_password: Database password
                - audio_dir: Directory for audio files (default: /tmp/audio)
        """
        self.groq_api_key = config['groq_api_key']
        self.audio_dir = config.get('audio_dir', '/tmp/audio')
        
        # PostgreSQL config
        self.postgres_config = {
            'host': config['postgres_host'],
            'port': config['postgres_port'],
            'dbname': config['postgres_db'],
            'user': config['postgres_user'],
            'password': config['postgres_password']
        }
        
        # Groq API endpoints
        self.groq_transcription_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        
        # Create audio directory
        os.makedirs(self.audio_dir, exist_ok=True)
        
        # Cleanup any leftover audio files from previous runs
        self.cleanup_old_audio()
        
        logger.info("ContentWatcher initialized")
    
    def get_db_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(**self.postgres_config)
    
    def cleanup_old_audio(self):
        """Cleanup any leftover audio files from previous runs."""
        import glob
        audio_files = glob.glob(os.path.join(self.audio_dir, "*.mp3"))
        audio_files += glob.glob(os.path.join(self.audio_dir, "*.webm"))
        audio_files += glob.glob(os.path.join(self.audio_dir, "*.wav"))
        
        for f in audio_files:
            try:
                os.remove(f)
                logger.info(f"Cleaned up old audio: {f}")
            except Exception as e:
                logger.warning(f"Could not remove {f}: {e}")
    
    def fetch_course_metadata(self, url: str) -> Dict:
        """
        Fetch course metadata using yt-dlp.
        
        Args:
            url: Course URL (YouTube playlist, LinkedIn Learning, etc.)
            
        Returns:
            Dictionary with course metadata
        """
        logger.info(f"Fetching metadata for: {url}")
        
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--flat-playlist',
            url
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Handle playlist vs single video
            courses = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    courses.append(json.loads(line))
            
            if not courses:
                # Single video
                cmd = ['yt-dlp', '--dump-json', url]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                courses = [json.loads(result.stdout)]
            
            logger.info(f"Found {len(courses)} videos")
            return {
                'title': courses[0].get('playlist_title', courses[0].get('title', 'Unknown')),
                'videos': courses,
                'total_videos': len(courses)
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error fetching metadata: {e}")
            raise
    
    def check_existing_subtitles(self, video_id: str) -> Optional[str]:
        """
        Check if video has existing subtitles.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Subtitle text if available, None otherwise
        """
        cmd = [
            'yt-dlp',
            '--write-sub',
            '--sub-lang', 'en',
            '--skip-download',
            '--sub-format', 'vtt',
            '-o', f'{self.audio_dir}/%(id)s',
            f'https://www.youtube.com/watch?v={video_id}'
        ]
        
        try:
            subprocess.run(cmd, capture_output=True, text=True)
            
            # Check if subtitle file was created
            subtitle_file = f"{self.audio_dir}/{video_id}.en.vtt"
            if os.path.exists(subtitle_file):
                with open(subtitle_file, 'r') as f:
                    content = f.read()
                os.remove(subtitle_file)
                return self.parse_vtt(content)
            
            return None
            
        except Exception as e:
            logger.warning(f"Error checking subtitles: {e}")
            return None
    
    def parse_vtt(self, vtt_content: str) -> str:
        """Parse VTT subtitle format to plain text."""
        lines = vtt_content.split('\n')
        text_lines = []
        
        for line in lines:
            # Skip timestamps and empty lines
            if '-->' in line or line.strip() == '' or line.startswith('WEBVTT'):
                continue
            # Remove HTML tags
            import re
            clean_line = re.sub(r'<[^>]+>', '', line).strip()
            if clean_line and clean_line not in text_lines[-1:]:
                text_lines.append(clean_line)
        
        return ' '.join(text_lines)
    
    def download_audio(self, video_url: str, video_id: str) -> str:
        """
        Download video and extract audio.
        
        Args:
            video_url: URL of the video
            video_id: Unique video identifier
            
        Returns:
            Path to downloaded audio file
        """
        output_path = f"{self.audio_dir}/{video_id}.%(ext)s"
        
        cmd = [
            'yt-dlp',
            '-x',  # Extract audio
            '--audio-format', 'mp3',
            '--audio-quality', '0',  # Best quality
            '-o', output_path,
            video_url
        ]
        
        logger.info(f"Downloading audio for: {video_id}")
        subprocess.run(cmd, check=True)
        
        audio_file = f"{self.audio_dir}/{video_id}.mp3"
        if os.path.exists(audio_file):
            logger.info(f"Downloaded: {audio_file}")
            return audio_file
        else:
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    def transcribe_with_groq(self, audio_path: str) -> str:
        """
        Transcribe audio using Groq Whisper API.
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        logger.info(f"Transcribing: {audio_path}")
        
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}"
        }
        
        with open(audio_path, 'rb') as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
            data = {
                "model": "whisper-large-v3",
                "language": "en",
                "response_format": "text"
            }
            
            response = requests.post(
                self.groq_transcription_url,
                headers=headers,
                files=files,
                data=data,
                timeout=300  # 5 minute timeout
            )
        
        if response.status_code == 200:
            transcript = response.text
            logger.info(f"Transcription complete: {len(transcript)} characters")
            return transcript
        else:
            logger.error(f"Transcription failed: {response.status_code} - {response.text}")
            raise Exception(f"Transcription failed: {response.text}")
    
    def store_transcript(self, course_name: str, provider: str, 
                         chapter_title: str, chapter_number: int,
                         transcript: str, duration_minutes: int,
                         video_url: str) -> None:
        """
        Store transcript in PostgreSQL.
        
        Args:
            course_name: Name of the course
            provider: Course provider (Google, Microsoft, etc.)
            chapter_title: Chapter/video title
            chapter_number: Chapter sequence number
            transcript: Transcribed text
            duration_minutes: Video duration in minutes
            video_url: Source video URL
        """
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            # Calculate word count
            word_count = len(transcript.split())
            
            cur.execute("""
                INSERT INTO workshop_transcripts 
                (course_name, provider, chapter_title, chapter_number, 
                 transcript, duration_minutes, video_url, word_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (course_name, provider, chapter_title, chapter_number,
                  transcript, duration_minutes, video_url, word_count))
            
            conn.commit()
            logger.info(f"Stored transcript: {chapter_title} ({word_count} words)")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing transcript: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def update_progress(self, course_name: str, videos_completed: int, 
                       hours_completed: float) -> None:
        """Update course progress in database."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                UPDATE course_progress 
                SET videos_completed = %s, 
                    hours_completed = %s,
                    status = 'transcribing',
                    updated_at = CURRENT_TIMESTAMP
                WHERE course_name = %s
            """, (videos_completed, hours_completed, course_name))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating progress: {e}")
        finally:
            cur.close()
            conn.close()
    
    def log_processing(self, agent_name: str, course_name: str, 
                      action: str, status: str, message: str = None) -> None:
        """Log processing activity."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO processing_logs 
                (agent_name, course_name, action, status, message)
                VALUES (%s, %s, %s, %s, %s)
            """, (agent_name, course_name, action, status, message))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
        finally:
            cur.close()
            conn.close()
    
    def process_course(self, course_url: str, provider: str = 'Unknown') -> Dict:
        """
        Main pipeline: Process an entire course.
        
        Args:
            course_url: URL of the course
            provider: Course provider name
            
        Returns:
            Processing results
        """
        start_time = datetime.now()
        
        try:
            # Fetch course metadata
            metadata = self.fetch_course_metadata(course_url)
            course_name = metadata['title']
            
            logger.info(f"Processing course: {course_name}")
            self.log_processing('agent1_watcher', course_name, 'started', 'processing')
            
            # Initialize progress
            total_videos = metadata['total_videos']
            total_hours = sum(v.get('duration', 0) for v in metadata['videos']) / 3600
            
            # Update or insert progress
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO course_progress 
                (course_name, provider, course_url, status, videos_total, hours_total)
                VALUES (%s, %s, %s, 'transcribing', %s, %s)
                ON CONFLICT (course_name) DO UPDATE SET
                    status = 'transcribing',
                    videos_total = %s,
                    hours_total = %s
            """, (course_name, provider, course_url, total_videos, total_hours,
                  total_videos, total_hours))
            conn.commit()
            cur.close()
            conn.close()
            
            # Process each video
            videos_completed = 0
            total_words = 0
            
            for i, video in enumerate(metadata['videos'], 1):
                video_id = video.get('id', f'video_{i}')
                video_title = video.get('title', f'Chapter {i}')
                video_url_video = video.get('url', f"https://www.youtube.com/watch?v={video_id}")
                duration = video.get('duration', 0) // 60  # Convert to minutes
                
                logger.info(f"Processing video {i}/{total_videos}: {video_title}")
                
                try:
                    # Check for existing subtitles first
                    transcript = self.check_existing_subtitles(video_id)
                    
                    if transcript:
                        logger.info(f"Using existing subtitles for: {video_title}")
                    else:
                        # Download audio
                        audio_path = self.download_audio(video_url_video, video_id)
                        
                        # Transcribe
                        transcript = self.transcribe_with_groq(audio_path)
                        
                        # ALWAYS cleanup audio file immediately after transcription
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                            logger.info(f"Cleaned up audio: {audio_path}")
                    
                    # Store transcript
                    self.store_transcript(
                        course_name=course_name,
                        provider=provider,
                        chapter_title=video_title,
                        chapter_number=i,
                        transcript=transcript,
                        duration_minutes=duration,
                        video_url=video_url_video
                    )
                    
                    videos_completed += 1
                    total_words += len(transcript.split())
                    
                    # Update progress
                    self.update_progress(
                        course_name,
                        videos_completed,
                        (duration * videos_completed) / 60
                    )
                    
                    logger.info(f"✅ Completed: {video_title}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing video {video_title}: {e}")
                    self.log_processing('agent1_watcher', course_name, 
                                       f'error_{video_title}', 'failed', str(e))
                    continue
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            
            # Update final status
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE course_progress 
                SET status = 'transcribed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE course_name = %s
            """, (course_name,))
            conn.commit()
            cur.close()
            conn.close()
            
            self.log_processing('agent1_watcher', course_name, 
                               'completed', 'success',
                               f"Processed {videos_completed} videos, {total_words} words")
            
            result = {
                'course_name': course_name,
                'videos_processed': videos_completed,
                'total_words': total_words,
                'duration_seconds': duration,
                'status': 'success'
            }
            
            logger.info(f"✅ Course completed: {course_name}")
            logger.info(f"   Videos: {videos_completed}/{total_videos}")
            logger.info(f"   Words: {total_words}")
            logger.info(f"   Duration: {duration:.1f}s")
            
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ Course processing failed: {e}")
            self.log_processing('agent1_watcher', course_name, 
                               'failed', 'error', str(e))
            
            return {
                'status': 'error',
                'error': str(e),
                'duration_seconds': duration
            }


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent 1: Content Watcher')
    parser.add_argument('url', help='Course URL to process')
    parser.add_argument('--provider', default='Unknown', help='Course provider')
    parser.add_argument('--groq-api-key', help='Groq API key')
    parser.add_argument('--postgres-host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--postgres-port', default='5432', help='PostgreSQL port')
    parser.add_argument('--postgres-db', default='certificate_tracker', help='Database name')
    parser.add_argument('--postgres-user', default='postgres', help='Database user')
    parser.add_argument('--postgres-password', default='postgres', help='Database password')
    
    args = parser.parse_args()
    
    # Use environment variable or argument
    groq_api_key = args.groq_api_key or os.environ.get('GROQ_API_KEY')
    if not groq_api_key:
        print("Error: GROQ_API_KEY not provided")
        return
    
    config = {
        'groq_api_key': groq_api_key,
        'postgres_host': args.postgres_host,
        'postgres_port': args.postgres_port,
        'postgres_db': args.postgres_db,
        'postgres_user': args.postgres_user,
        'postgres_password': args.postgres_password
    }
    
    watcher = ContentWatcher(config)
    result = watcher.process_course(args.url, args.provider)
    
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
