#!/usr/bin/env python3
"""
Agent 2: Content Summarizer (RAG Engine)
Processes transcripts from PostgreSQL and generates study materials
using Retrieval-Augmented Generation with configurable LLM providers.

Supports: Ollama, OpenAI, Anthropic, DeepSeek, Groq
Falls back to text-only summarization if no provider is available.
"""

import os
import sys
import json
import psycopg2
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

# Add parent directory to path for provider imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from providers import create_provider, list_providers, LLMProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ContentSummarizer')


class ContentSummarizer:
    """
    Agent 2: RAG-based content summarizer.
    
    Pipeline:
    1. Load transcripts from PostgreSQL
    2. Chunk content for processing
    3. Generate embeddings for RAG (if provider supports it)
    4. Generate summaries using configured LLM provider
    5. Create study materials
    """
    
    def __init__(self, config: Dict):
        """
        Initialize ContentSummarizer with configuration.
        
        Args:
            config: Dictionary containing:
                - provider: LLM provider name ('ollama', 'openai', 'anthropic', 'deepseek', 'groq')
                - postgres_host: PostgreSQL host
                - postgres_port: PostgreSQL port
                - postgres_db: Database name
                - postgres_user: Database user
                - postgres_password: Database password
                - output_dir: Output directory for materials
                - chunk_size: Text chunk size (default: 2000)
                - chunk_overlap: Chunk overlap (default: 200)
        """
        self.output_dir = config.get('output_dir', './output')
        
        # PostgreSQL config
        self.postgres_config = {
            'host': config.get('postgres_host', 'localhost'),
            'port': config.get('postgres_port', '5432'),
            'dbname': config.get('postgres_db', 'certificate_tracker'),
            'user': config.get('postgres_user', 'postgres'),
            'password': config.get('postgres_password', 'postgres')
        }
        
        # Text chunking settings
        self.chunk_size = config.get('chunk_size', 2000)
        self.chunk_overlap = config.get('chunk_overlap', 200)
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize LLM provider
        self.provider = None
        provider_name = config.get('provider') or os.environ.get('LLM_PROVIDER', 'groq')
        
        try:
            provider_config = {
                'ollama_url': config.get('ollama_url', os.environ.get('OLLAMA_URL', 'http://localhost:11434')),
                'ollama_model': config.get('ollama_model', os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')),
                'openai_api_key': config.get('openai_api_key', os.environ.get('OPENAI_API_KEY', '')),
                'openai_model': config.get('openai_model', os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')),
                'openai_base_url': config.get('openai_base_url', os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')),
                'anthropic_api_key': config.get('anthropic_api_key', os.environ.get('ANTHROPIC_API_KEY', '')),
                'anthropic_model': config.get('anthropic_model', os.environ.get('ANTHROPIC_MODEL', 'claude-3-5-sonnet-20241022')),
                'deepseek_api_key': config.get('deepseek_api_key', os.environ.get('DEEPSEEK_API_KEY', '')),
                'deepseek_model': config.get('deepseek_model', os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')),
                'groq_api_key': config.get('groq_api_key', os.environ.get('GROQ_API_KEY', '')),
                'groq_model': config.get('groq_model', os.environ.get('GROQ_MODEL', 'llama3-70b-8192')),
            }
            
            self.provider = create_provider(provider_name, provider_config)
            
            if self.provider.is_available():
                info = self.provider.get_model_info()
                logger.info(f"✅ LLM Provider: {info['provider']} ({info['model']}) - {info['type']}")
            else:
                logger.warning(f"⚠️  Provider '{provider_name}' is configured but not available")
                logger.warning("   Falling back to text-only summarization")
                self.provider = None
                
        except Exception as e:
            logger.warning(f"⚠️  Could not initialize LLM provider: {e}")
            logger.warning("   Using text-only summarization mode")
            self.provider = None
        
        if self.provider is None:
            logger.info("📝 Running in TEXT-ONLY mode (no LLM - summaries will be raw transcripts)")
    
    def get_db_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(**self.postgres_config)
    
    def load_transcripts(self, course_name: str) -> List[Dict]:
        """Load transcripts from PostgreSQL."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, chapter_title, chapter_number, transcript, 
                       duration_minutes, word_count
                FROM workshop_transcripts
                WHERE course_name = %s
                ORDER BY chapter_number
            """, (course_name,))
            
            transcripts = []
            for row in cur.fetchall():
                transcripts.append({
                    'id': row[0],
                    'chapter_title': row[1],
                    'chapter_number': row[2],
                    'transcript': row[3],
                    'duration_minutes': row[4],
                    'word_count': row[5]
                })
            
            logger.info(f"Loaded {len(transcripts)} transcripts for: {course_name}")
            return transcripts
            
        finally:
            cur.close()
            conn.close()
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap."""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + self.chunk_size
            
            if end < text_length:
                for separator in ['. ', '.\n', '! ', '? ', '\n\n']:
                    last_sep = text[start:end].rfind(separator)
                    if last_sep > self.chunk_size // 2:
                        end = start + last_sep + len(separator)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
        
        return chunks
    
    def generate_with_llm(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate text using configured LLM provider.
        Falls back to text-only mode if no provider available.
        """
        if self.provider is None:
            # Text-only fallback: return the prompt content as-is (truncated summary)
            return self._text_only_summary(prompt)
        
        try:
            return self.provider.generate_with_retry(prompt, system_prompt)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            logger.info("Falling back to text-only summary")
            return self._text_only_summary(prompt)
    
    def _text_only_summary(self, prompt: str) -> str:
        """
        Text-only fallback when no LLM is available.
        Extracts key sentences from the transcript.
        """
        # Extract lines that look like key content
        lines = prompt.split('\n')
        key_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip very short lines, timestamps, headers
            if len(line) < 20:
                continue
            if '-->' in line or line.startswith('WEBVTT'):
                continue
            # Keep lines that seem like content
            key_lines.append(line)
        
        if not key_lines:
            return "No summary available (text-only mode)"
        
        # Take first ~500 words as summary
        summary = ' '.join(key_lines)
        words = summary.split()
        if len(words) > 500:
            summary = ' '.join(words[:500]) + '...'
        
        return summary
    
    def summarize_chapter(self, chapter_title: str, transcript: str) -> str:
        """Generate summary for a chapter."""
        system_prompt = """You are an expert educator creating study materials.
Always provide comprehensive, well-structured summaries.
Use bullet points, headers, and clear organization.
Focus on key concepts, definitions, and practical applications."""
        
        prompt = f"""Create a detailed summary of this workshop chapter.

Chapter: {chapter_title}

Transcript:
{transcript[:8000]}

Include:
1. Main topic and learning objectives
2. Key concepts (bullet points with explanations)
3. Important definitions
4. Practical examples mentioned
5. Key takeaways
6. Common pitfalls to avoid

Summary:"""
        
        return self.generate_with_llm(prompt, system_prompt)
    
    def extract_key_concepts(self, course_name: str, transcripts: List[Dict]) -> str:
        """Extract key technical concepts from all transcripts."""
        all_text = "\n\n".join([
            f"## {t['chapter_title']}\n{t['transcript'][:3000]}" 
            for t in transcripts[:10]
        ])
        
        system_prompt = """You are an expert educator extracting key concepts.
Always provide clear definitions and practical examples.
Organize concepts by category when possible."""
        
        prompt = f"""Extract all key technical concepts from this course content.

Course: {course_name}

Content:
{all_text[:12000]}

For each concept provide:
1. **Concept Name**
2. **Definition** (1-2 clear sentences)
3. **When to Use** (practical context)
4. **Example** (concrete example)
5. **Related Concepts** (connections to other topics)

Group related concepts together. Focus on the most important concepts first.

Key Concepts:"""
        
        return self.generate_with_llm(prompt, system_prompt)
    
    def generate_cheat_sheet(self, course_name: str, summaries: List[str]) -> str:
        """Generate a quick reference cheat sheet."""
        combined = "\n\n".join([
            f"### Chapter {i+1}\n{summary[:2000]}" 
            for i, summary in enumerate(summaries[:10])
        ])
        
        system_prompt = """You are creating a concise cheat sheet.
Keep it brief but comprehensive.
Use bullet points, tables, and clear formatting.
Focus on the most essential information."""
        
        prompt = f"""Create a quick reference cheat sheet for this course.

Course: {course_name}

Summaries:
{combined[:10000]}

Create a cheat sheet that includes:
1. **Key Terms** (one-line definitions)
2. **Important Formulas/Concepts** (if applicable)
3. **Common Patterns** (best practices)
4. **Quick Tips** (exam-ready points)
5. **Dos and Don'ts**

Keep it concise - this should fit on 2-3 pages.

Cheat Sheet:"""
        
        return self.generate_with_llm(prompt, system_prompt)
    
    def generate_study_guide(self, course_name: str, transcripts: List[Dict]) -> str:
        """Generate comprehensive study guide."""
        study_guide = f"# Study Guide: {course_name}\n\n"
        study_guide += f"*Generated on {datetime.now().strftime('%Y-%m-%d')}*\n\n"
        
        if self.provider:
            info = self.provider.get_model_info()
            study_guide += f"*Provider: {info['provider']} ({info['model']})*\n\n"
        else:
            study_guide += "*Mode: Text-only (no LLM provider)*\n\n"
        
        study_guide += "---\n\n"
        
        for i, transcript in enumerate(transcripts, 1):
            logger.info(f"Summarizing chapter {i}/{len(transcripts)}: {transcript['chapter_title']}")
            
            summary = self.summarize_chapter(
                transcript['chapter_title'], 
                transcript['transcript']
            )
            
            study_guide += f"## Chapter {i}: {transcript['chapter_title']}\n\n"
            study_guide += f"*Duration: {transcript['duration_minutes']} minutes*\n\n"
            study_guide += summary + "\n\n"
            study_guide += "---\n\n"
        
        key_concepts = self.extract_key_concepts(course_name, transcripts)
        study_guide += "## Key Concepts Summary\n\n"
        study_guide += key_concepts + "\n\n"
        
        return study_guide
    
    def store_summary(self, course_name: str, summary_type: str, 
                     content: str, chapter: str = None) -> None:
        """Store summary in database."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            model_used = self.provider.get_model_info()['model'] if self.provider else 'text-only'
            cur.execute("""
                INSERT INTO ai_summaries 
                (course_name, summary_type, chapter, summary_content, word_count, model_used)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (course_name, summary_type, chapter, content, 
                  len(content.split()), model_used))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing summary: {e}")
        finally:
            cur.close()
            conn.close()
    
    def store_material(self, course_name: str, material_type: str, 
                      content: str, file_path: str) -> None:
        """Store generated material in database."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO generated_materials 
                (course_name, material_type, file_path, content, word_count)
                VALUES (%s, %s, %s, %s, %s)
            """, (course_name, material_type, file_path, content, 
                  len(content.split())))
            
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing material: {e}")
        finally:
            cur.close()
            conn.close()
    
    def save_to_file(self, content: str, file_path: str) -> None:
        """Save content to markdown file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Saved: {file_path}")
    
    def process_course(self, course_name: str) -> Dict:
        """
        Main pipeline: Process an entire course.
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Processing course: {course_name}")
            
            # Update status
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE course_progress 
                SET status = 'summarizing'
                WHERE course_name = %s
            """, (course_name,))
            conn.commit()
            cur.close()
            conn.close()
            
            # Load transcripts
            transcripts = self.load_transcripts(course_name)
            if not transcripts:
                raise ValueError(f"No transcripts found for: {course_name}")
            
            # Create output directory (sanitize name for Windows)
            safe_name = course_name.replace(':', '').replace('|', '').replace('?', '').replace('*', '').replace('"', '').replace('<', '').replace('>', '')
            course_dir = os.path.join(self.output_dir, safe_name)
            os.makedirs(course_dir, exist_ok=True)
            
            # Step 1: Store transcript chunks for RAG
            logger.info("Step 1: Storing transcript chunks for RAG...")
            for transcript in transcripts:
                chunks = self.chunk_text(transcript['transcript'])
                if chunks:
                    conn = self.get_db_connection()
                    cur = conn.cursor()
                    for i, chunk in enumerate(chunks):
                        cur.execute("""
                            INSERT INTO chunk_embeddings 
                            (course_name, chapter, chapter_number, chunk_index, 
                             content, embedding, token_count)
                            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                        """, (course_name, transcript['chapter_title'], 
                              transcript['chapter_number'], i,
                              chunk, json.dumps([]), len(chunk.split())))
                    conn.commit()
                    cur.close()
                    conn.close()
                    logger.info(f"  Stored {len(chunks)} chunks for: {transcript['chapter_title']}")
            
            # Step 2: Generate chapter summaries
            logger.info("Step 2: Generating chapter summaries...")
            summaries = []
            for transcript in transcripts:
                summary = self.summarize_chapter(
                    transcript['chapter_title'],
                    transcript['transcript']
                )
                summaries.append(summary)
                self.store_summary(
                    course_name, 'chapter', summary, 
                    transcript['chapter_title']
                )
            
            # Step 3: Generate study guide
            logger.info("Step 3: Generating study guide...")
            study_guide = self.generate_study_guide(course_name, transcripts)
            study_guide_path = os.path.join(course_dir, 'study-guide.md')
            self.save_to_file(study_guide, study_guide_path)
            self.store_material(course_name, 'study_guide', study_guide, study_guide_path)
            
            # Step 4: Generate cheat sheet
            logger.info("Step 4: Generating cheat sheet...")
            cheat_sheet = self.generate_cheat_sheet(course_name, summaries)
            cheat_sheet_path = os.path.join(course_dir, 'cheat-sheet.md')
            self.save_to_file(cheat_sheet, cheat_sheet_path)
            self.store_material(course_name, 'cheat_sheet', cheat_sheet, cheat_sheet_path)
            
            # Step 5: Extract key concepts
            logger.info("Step 5: Extracting key concepts...")
            key_concepts = self.extract_key_concepts(course_name, transcripts)
            key_concepts_path = os.path.join(course_dir, 'key-concepts.md')
            self.save_to_file(key_concepts, key_concepts_path)
            self.store_material(course_name, 'key_concepts', key_concepts, key_concepts_path)
            
            # Update progress
            duration = (datetime.now() - start_time).total_seconds()
            
            conn = self.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE course_progress 
                SET status = 'completed',
                    study_guide_ready = TRUE,
                    cheat_sheet_ready = TRUE,
                    key_concepts_ready = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE course_name = %s
            """, (course_name,))
            conn.commit()
            cur.close()
            conn.close()
            
            provider_info = self.provider.get_model_info() if self.provider else {'provider': 'text-only', 'model': 'none'}
            
            result = {
                'course_name': course_name,
                'chapters_processed': len(transcripts),
                'provider': provider_info['provider'],
                'model': provider_info['model'],
                'materials_generated': [
                    'study-guide.md',
                    'cheat-sheet.md',
                    'key-concepts.md'
                ],
                'output_directory': course_dir,
                'duration_seconds': duration,
                'status': 'success'
            }
            
            logger.info(f"✅ Course completed: {course_name}")
            logger.info(f"   Provider: {provider_info['provider']} ({provider_info['model']})")
            logger.info(f"   Chapters: {len(transcripts)}")
            logger.info(f"   Materials: {len(result['materials_generated'])}")
            logger.info(f"   Duration: {duration:.1f}s")
            
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ Course processing failed: {e}")
            
            return {
                'status': 'error',
                'error': str(e),
                'duration_seconds': duration
            }
    
    def rag_query(self, question: str, course_name: str) -> str:
        """Answer a question using RAG."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT content, chapter
                FROM chunk_embeddings
                WHERE course_name = %s
                AND (
                    content ILIKE %s
                    OR chapter ILIKE %s
                )
                LIMIT 5
            """, (course_name, f'%{question}%', f'%{question}%'))
            
            results = cur.fetchall()
            
            if not results:
                return "No relevant content found for this question."
            
            context = "\n\n---\n\n".join([
                f"**{row[1]}**:\n{row[0]}"
                for row in results
            ])
            
            system_prompt = """You are a helpful assistant answering questions about course content.
Use only the provided context to answer.
If the context doesn't contain the answer, say so clearly.
Be concise but thorough."""
            
            prompt = f"""Answer this question based on the course content.

Question: {question}

Context from course:
{context}

Answer:"""
            
            return self.generate_with_llm(prompt, system_prompt)
            
        finally:
            cur.close()
            conn.close()


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent 2: Content Summarizer')
    parser.add_argument('course_name', help='Course name to process')
    parser.add_argument('--provider', choices=['ollama', 'openai', 'anthropic', 'deepseek', 'groq'],
                       help='LLM provider (default: from env LLM_PROVIDER or groq)')
    parser.add_argument('--output-dir', default='./output', help='Output directory')
    parser.add_argument('--postgres-host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--postgres-port', default='5432', help='PostgreSQL port')
    parser.add_argument('--postgres-db', default='certificate_tracker', help='Database name')
    parser.add_argument('--postgres-user', default='postgres', help='Database user')
    parser.add_argument('--postgres-password', default='postgres', help='Database password')
    parser.add_argument('--list-providers', action='store_true', help='List available providers')
    
    args = parser.parse_args()
    
    if args.list_providers:
        print("\nAvailable LLM Providers:")
        print("=" * 50)
        providers = list_providers()
        for name, info in providers.items():
            status = "✅ Available" if info['available'] else "❌ Not available"
            print(f"  {name:12} {status}")
            if 'info' in info:
                print(f"               Model: {info['info'].get('model', 'N/A')}")
            if 'error' in info:
                print(f"               Error: {info['error']}")
        print()
        return
    
    config = {
        'provider': args.provider,
        'output_dir': args.output_dir,
        'postgres_host': args.postgres_host,
        'postgres_port': args.postgres_port,
        'postgres_db': args.postgres_db,
        'postgres_user': args.postgres_user,
        'postgres_password': args.postgres_password,
    }
    
    summarizer = ContentSummarizer(config)
    result = summarizer.process_course(args.course_name)
    
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
