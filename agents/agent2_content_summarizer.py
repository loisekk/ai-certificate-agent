#!/usr/bin/env python3
"""
Agent 2: Content Summarizer (RAG Engine)
Processes transcripts from PostgreSQL and generates study materials
using Retrieval-Augmented Generation (RAG) with Ollama.
"""

import os
import json
import psycopg2
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

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
    3. Generate embeddings for RAG
    4. Generate summaries using Ollama
    5. Create study materials
    """
    
    def __init__(self, config: Dict):
        """
        Initialize ContentSummarizer with configuration.
        
        Args:
            config: Dictionary containing:
                - ollama_url: Ollama API URL (default: http://localhost:11434)
                - ollama_model: LLM model name (default: llama3)
                - embedding_model: Embedding model (default: nomic-embed-text)
                - postgres_host: PostgreSQL host
                - postgres_port: PostgreSQL port
                - postgres_db: Database name
                - postgres_user: Database user
                - postgres_password: Database password
                - output_dir: Output directory for materials
        """
        self.ollama_url = config.get('ollama_url', 'http://localhost:11434')
        self.ollama_model = config.get('ollama_model', 'llama3')
        self.embedding_model = config.get('embedding_model', 'nomic-embed-text')
        self.output_dir = config.get('output_dir', './output')
        
        # PostgreSQL config
        self.postgres_config = {
            'host': config['postgres_host'],
            'port': config['postgres_port'],
            'dbname': config['postgres_db'],
            'user': config['postgres_user'],
            'password': config['postgres_password']
        }
        
        # Text chunking settings
        self.chunk_size = config.get('chunk_size', 2000)
        self.chunk_overlap = config.get('chunk_overlap', 200)
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info("ContentSummarizer initialized")
        logger.info(f"Ollama URL: {self.ollama_url}")
        logger.info(f"Model: {self.ollama_model}")
    
    def get_db_connection(self):
        """Get PostgreSQL connection."""
        return psycopg2.connect(**self.postgres_config)
    
    def load_transcripts(self, course_name: str) -> List[Dict]:
        """
        Load transcripts from PostgreSQL.
        
        Args:
            course_name: Name of the course
            
        Returns:
            List of transcript dictionaries
        """
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
        """
        Split text into chunks with overlap.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < text_length:
                # Look for sentence end
                for separator in ['. ', '.\n', '! ', '? ', '\n\n']:
                    last_sep = text[start:end].rfind(separator)
                    if last_sep > self.chunk_size // 2:
                        end = start + last_sep + len(separator)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start with overlap
            start = end - self.chunk_overlap
        
        return chunks
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using Ollama.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        
        for text in texts:
            try:
                response = requests.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={
                        "model": self.embedding_model,
                        "prompt": text
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    embedding = response.json()['embedding']
                    embeddings.append(embedding)
                else:
                    logger.error(f"Embedding failed: {response.status_code}")
                    embeddings.append([0.0] * 768)  # Default dimension
                    
            except Exception as e:
                logger.error(f"Embedding error: {e}")
                embeddings.append([0.0] * 768)
        
        return embeddings
    
    def store_embeddings(self, course_name: str, chapter: str, 
                        chapter_number: int, chunks: List[str], 
                        embeddings: List[List[float]]) -> None:
        """Store embeddings in PostgreSQL."""
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                cur.execute("""
                    INSERT INTO chunk_embeddings 
                    (course_name, chapter, chapter_number, chunk_index, 
                     content, embedding, token_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (course_name, chapter, chapter_number, i,
                      chunk, str(embedding), len(chunk.split())))
            
            conn.commit()
            logger.info(f"Stored {len(chunks)} embeddings for: {chapter}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing embeddings: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    def generate_with_ollama(self, prompt: str, system_prompt: str = None) -> str:
        """
        Generate text using Ollama.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": messages,
                    "stream": False
                },
                timeout=300  # 5 minute timeout
            )
            
            if response.status_code == 200:
                return response.json()['message']['content']
            else:
                logger.error(f"Ollama error: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return ""
    
    def summarize_chapter(self, chapter_title: str, transcript: str) -> str:
        """
        Generate summary for a chapter.
        
        Args:
            chapter_title: Chapter title
            transcript: Chapter transcript
            
        Returns:
            Chapter summary
        """
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
        
        return self.generate_with_ollama(prompt, system_prompt)
    
    def extract_key_concepts(self, course_name: str, transcripts: List[Dict]) -> str:
        """
        Extract key technical concepts from all transcripts.
        
        Args:
            course_name: Course name
            transcripts: List of transcripts
            
        Returns:
            Key concepts document
        """
        # Combine all transcripts (limited to avoid context overflow)
        all_text = "\n\n".join([
            f"## {t['chapter_title']}\n{t['transcript'][:3000]}" 
            for t in transcripts[:10]  # Limit to first 10 chapters
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
        
        return self.generate_with_ollama(prompt, system_prompt)
    
    def generate_cheat_sheet(self, course_name: str, summaries: List[str]) -> str:
        """
        Generate a quick reference cheat sheet.
        
        Args:
            course_name: Course name
            summaries: List of chapter summaries
            
        Returns:
            Cheat sheet content
        """
        # Combine summaries
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
        
        return self.generate_with_ollama(prompt, system_prompt)
    
    def generate_study_guide(self, course_name: str, transcripts: List[Dict]) -> str:
        """
        Generate comprehensive study guide.
        
        Args:
            course_name: Course name
            transcripts: List of transcripts
            
        Returns:
            Study guide content
        """
        system_prompt = """You are an expert educator creating comprehensive study guides.
Use clear organization with headers and subheaders.
Include detailed explanations with examples.
Make it suitable for exam preparation."""
        
        # Process each chapter
        study_guide = f"# Study Guide: {course_name}\n\n"
        study_guide += f"*Generated on {datetime.now().strftime('%Y-%m-%d')}*\n\n"
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
        
        # Add key concepts section
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
            cur.execute("""
                INSERT INTO ai_summaries 
                (course_name, summary_type, chapter, summary_content, word_count, model_used)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (course_name, summary_type, chapter, content, 
                  len(content.split()), self.ollama_model))
            
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
        
        Args:
            course_name: Name of the course
            
        Returns:
            Processing results
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
            
            # Create output directory
            course_dir = os.path.join(self.output_dir, course_name)
            os.makedirs(course_dir, exist_ok=True)
            
            # Step 1: Generate embeddings for RAG
            logger.info("Step 1: Generating embeddings...")
            for transcript in transcripts:
                chunks = self.chunk_text(transcript['transcript'])
                if chunks:
                    embeddings = self.generate_embeddings(chunks)
                    self.store_embeddings(
                        course_name,
                        transcript['chapter_title'],
                        transcript['chapter_number'],
                        chunks,
                        embeddings
                    )
            
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
            
            result = {
                'course_name': course_name,
                'chapters_processed': len(transcripts),
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
        """
        Answer a question using RAG.
        
        Args:
            question: User question
            course_name: Course to search in
            
        Returns:
            Answer based on course content
        """
        # Generate question embedding
        q_embedding = self.generate_embeddings([question])[0]
        
        # Search similar chunks
        conn = self.get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT content, chapter, 
                       1 - (embedding <=> %s::vector) as similarity
                FROM chunk_embeddings
                WHERE course_name = %s
                ORDER BY similarity DESC
                LIMIT 5
            """, (str(q_embedding), course_name))
            
            results = cur.fetchall()
            
            if not results:
                return "No relevant content found for this question."
            
            # Build context
            context = "\n\n---\n\n".join([
                f"**{row[1]}** (similarity: {row[2]:.2f}):\n{row[0]}"
                for row in results
            ])
            
            # Generate answer
            system_prompt = """You are a helpful assistant answering questions about course content.
Use only the provided context to answer.
If the context doesn't contain the answer, say so clearly.
Be concise but thorough."""
            
            prompt = f"""Answer this question based on the course content.

Question: {question}

Context from course:
{context}

Answer:"""
            
            return self.generate_with_ollama(prompt, system_prompt)
            
        finally:
            cur.close()
            conn.close()


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent 2: Content Summarizer')
    parser.add_argument('course_name', help='Course name to process')
    parser.add_argument('--ollama-url', default='http://localhost:11434', 
                       help='Ollama API URL')
    parser.add_argument('--ollama-model', default='llama3', help='LLM model')
    parser.add_argument('--embedding-model', default='nomic-embed-text',
                       help='Embedding model')
    parser.add_argument('--output-dir', default='./output', help='Output directory')
    parser.add_argument('--postgres-host', default='localhost', help='PostgreSQL host')
    parser.add_argument('--postgres-port', default='5432', help='PostgreSQL port')
    parser.add_argument('--postgres-db', default='certificate_tracker', help='Database name')
    parser.add_argument('--postgres-user', default='postgres', help='Database user')
    parser.add_argument('--postgres-password', default='postgres', help='Database password')
    
    args = parser.parse_args()
    
    config = {
        'ollama_url': args.ollama_url,
        'ollama_model': args.ollama_model,
        'embedding_model': args.embedding_model,
        'output_dir': args.output_dir,
        'postgres_host': args.postgres_host,
        'postgres_port': args.postgres_port,
        'postgres_db': args.postgres_db,
        'postgres_user': args.postgres_user,
        'postgres_password': args.postgres_password
    }
    
    summarizer = ContentSummarizer(config)
    result = summarizer.process_course(args.course_name)
    
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
