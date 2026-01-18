
import os
import time
import threading
import json
import logging
import fnmatch
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import numpy as np

# Conditional imports to avoid crashing if dependencies are missing during dev
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    faiss = None
    SentenceTransformer = None
    Observer = None
    FileSystemEventHandler = object

from src.utils.logger import get_logger

logger = get_logger()

# --- CONSTANTS ---
MODEL_NAME = 'all-MiniLM-L6-v2'
VECTOR_DIM = 384  # Dimension for MiniLM-L6-v2
INDEX_FILE = "search_index.faiss"
METADATA_FILE = "search_metadata.json"

class SearchEngine(FileSystemEventHandler):
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SearchEngine, cls).__new__(cls)
                    cls._instance.initialized = False
        return cls._instance

    def initialize(self, root_dir: Path, persist_dir: Path, watch: bool = True):
        """
        Initialize the search engine.
        """
        if self.initialized:
            return

        self.root_dir = root_dir
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.persist_dir / INDEX_FILE
        self.metadata_path = self.persist_dir / METADATA_FILE
        
        self.model = None
        self.index = None
        self.file_paths = [] 
        self.chunk_map = [] 
        self.last_reload = 0
        self.device = "cpu"
        
        # Check Dependencies
        if not (faiss and SentenceTransformer and Observer):
            logger.error("Search", "Missing dependencies (faiss/sentence_transformers/watchdog). Search disabled.")
            return

        logger.log("INFO", "Search", f"Initializing Search Engine with {MODEL_NAME} (Watch={watch})...")
        
        # Load Model
        try:
            self.model = SentenceTransformer(MODEL_NAME, device='cuda') # Try CUDA
            self.device = "cuda”"
        except:
            try:
                self.model = SentenceTransformer(MODEL_NAME, device='cpu')
                self.device = "cpu"
            except:
                return
        
        logger.log("INFO", "Search", f"Model loaded on {self.device.upper()}")


        # Load Index
        self._load_index()
        
        # Start Watcher if requested
        if watch:
            self.observer = Observer()
            self.observer.schedule(self, str(self.root_dir), recursive=True)
            self.observer.start()
            
            # Initial scan if empty
            if self.index.ntotal == 0:
                threading.Thread(target=self._full_scan, daemon=True).start()
                
        self.initialized = True

    def _load_index(self):
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                # Check consistency
                mtime = self.metadata_path.stat().st_mtime
                if mtime <= self.last_reload: return
                
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.chunk_map = data.get("chunks", [])
                
                self.last_reload = mtime
                logger.log("INFO", "Search", f"Loaded index ({self.index.ntotal} vectors).")
            except Exception as e:
                logger.error("Search", f"Error loading index: {e}. Resetting.")
                self.index = faiss.IndexFlatL2(VECTOR_DIM)
                self.chunk_map = []
        else:
            self.index = faiss.IndexFlatL2(VECTOR_DIM)
            self.chunk_map = []

    def _check_reload(self):
        """Reloads index if file changed on disk."""
        if self.metadata_path.exists():
            mtime = self.metadata_path.stat().st_mtime
            if mtime > self.last_reload:
                 self._load_index()

    # ... (rest of class) ...


    def _save_index(self):
        if not self.index: return
        try:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump({"chunks": self.chunk_map}, f)
        except Exception as e:
            logger.error("Search", f"Error saving index: {e}")

    def _full_scan(self):
        """Scans all files and indexes them."""
        logger.log("INFO", "Search", "Starting full file scan...")
        all_files = []
        for root, dirs, files in os.walk(self.root_dir):
            # Skip hidden dirs and system dir
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', 'env']]
            
            # Explicit exclusion
            if ".multi-agent-mcp" in root:
                continue
            
            for file in files:
                if file.startswith('.'): continue
                # Filter extensions
                if not file.endswith(('.py', '.md', '.json', '.js', '.ts', '.html', '.css', '.txt', '.toml')):
                    continue
                    
                full_path = Path(root) / file
                try:
                    rel_path = full_path.relative_to(self.root_dir)
                    # Double check relative path does not start with excluded
                    if str(rel_path).startswith(".multi-agent-mcp"): continue
                    all_files.append(rel_path)
                except: pass
        
        # Process files
        new_chunks = []
        new_vectors = []
        
        for p in all_files:
            chunks, vectors = self._process_file(p)
            if chunks:
                new_chunks.extend(chunks)
                new_vectors.append(vectors)
        
        if new_vectors:
            flat_vectors = np.vstack(new_vectors)
            self.index = faiss.IndexFlatL2(VECTOR_DIM) # Reset
            self.index.add(flat_vectors)
            self.chunk_map = new_chunks
            self._save_index()
            
        logger.log("INFO", "Search", f"Scan complete. Indexed {len(self.chunk_map)} chunks.")

    def _process_file(self, rel_path: Path) -> Tuple[List[dict], Optional[np.ndarray]]:
        """Reads a file, chunks it, and returns metadata and vectors."""
        full_path = self.root_dir / rel_path
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return [], None
            
        # Simple Chunking (Line based for code)
        lines = content.splitlines()
        chunks = []
        chunk_texts = []
        
        # Configurable chunk size
        CHUNK_SIZE = 50 
        OVERLAP = 10
        
        for i in range(0, len(lines), CHUNK_SIZE - OVERLAP):
            chunk_lines = lines[i:i+CHUNK_SIZE]
            if not chunk_lines: break
            
            text_block = "\n".join(chunk_lines)
            if not text_block.strip(): continue
            
            # Metadata
            chunks.append({
                "path": str(rel_path),
                "content": text_block,
                "start_line": i + 1,
                "end_line": i + len(chunk_lines)
            })
            
            # Enrich text for embedding (include path)
            chunk_texts.append(f"File: {rel_path}\nContent:\n{text_block}")
            
        if not chunk_texts:
            return [], None
            
        embeddings = self.model.encode(chunk_texts)
        return chunks, embeddings

    # --- Watchdog Handling ---
    def on_modified(self, event):
        if event.is_directory: return
        self._handle_change(event.src_path)
        
    def on_created(self, event):
        if event.is_directory: return
        self._handle_change(event.src_path)

    def _handle_change(self, file_path):
        try:
            path = Path(file_path)
            # Filter
            if path.name.startswith('.') or not path.suffix in ['.py', '.md', '.json', '.js', '.ts', '.html', '.css', '.txt', '.toml']:
                return
            
            rel_path = path.relative_to(self.root_dir)
            
            if str(rel_path).startswith(".multi-agent-mcp"): 
                return
            
            logger.log("INFO", "Search", f"File changed: {rel_path}. Updating index...")
            chunks, vectors = self._process_file(rel_path)
            if chunks and vectors is not None:
                self.index.add(vectors)
                self.chunk_map.extend(chunks) 
                self._save_index()
                
        except Exception as e:
            logger.error("Search", f"Error handling file change: {e}")

    # --- Public API ---

    def search(self, query: str, limit: int = 5, file_pattern: str = None) -> List[dict]:
        self._check_reload()
        
        if not self.initialized or not self.index or self.index.ntotal == 0:
            return []
            
        query_vector = self.model.encode([query])
        D, I = self.index.search(query_vector, limit * 4) 
        
        results = []
        seen_content_hashes = set()
        
        for i, idx in enumerate(I[0]):
            if idx == -1 or idx >= len(self.chunk_map): continue
            
            chunk = self.chunk_map[idx]
            
            # Filter Pattern
            if file_pattern and not fnmatch.fnmatch(chunk['path'], file_pattern):
                continue
                
            # Deduplication (exact content)
            h = hash(chunk['content'])
            if h in seen_content_hashes: continue
            seen_content_hashes.add(h)
            
            # Score
            score = float(D[0][i])
            
            results.append({
                "path": chunk['path'],
                "start_line": chunk['start_line'],
                "end_line": chunk['end_line'],
                "content": chunk['content'],
                "score": score
            })
            
            if len(results) >= limit:
                break
                
        return results

    def get_relevant_context(self, query: str, max_markdown: int = 2, max_total: int = 5) -> Tuple[str, List[dict]]:
        """
        Returns a formatted string for markdown injection and the raw results list.
        Sensitive to passive constraints: ONLY .md or .txt files.
        """
        # We query more to filter
        results = self.search(query, limit=max_total * 2) 
        if not results:
            return "", []
            
        # Filter for Passive Context: Only .md and .txt
        valid_results = []
        for r in results:
            if r['path'].endswith(('.md', '.txt')):
                valid_results.append(r)
                
        markdown_results = valid_results[:max_markdown]
        
        md_output = []
        for r in markdown_results:
            ext = Path(r['path']).suffix.lstrip('.')
            md_output.append(f"**{r['path']}** (L{r['start_line']}-{r['end_line']})\n```{ext}\n{r['content']}\n```")
            
        return "\n\n".join(md_output), valid_results

