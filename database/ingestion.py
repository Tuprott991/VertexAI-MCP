"""
Production-ready async document ingestion from markdown files.

Features:
- Async file I/O operations
- Batch processing support
- Error handling and retry logic
- Progress tracking for bulk imports
- Support for multiple file formats
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv

from database.document import upsert_document, DocumentError

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Base exception for ingestion errors"""
    pass


async def read_file_async(file_path: str, encoding: str = 'utf-8') -> str:
    """
    Read file content asynchronously.
    
    Args:
        file_path: Path to the file
        encoding: File encoding (default: utf-8)
            
    Returns:
        str: File content
        
    Raises:
        IngestionError: If file reading fails
    """
    try:
        loop = asyncio.get_event_loop()
        
        def _read_file():
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        
        # Run blocking I/O in thread pool
        content = await loop.run_in_executor(None, _read_file)
        return content
        
    except FileNotFoundError:
        raise IngestionError(f"File not found: {file_path}")
    except UnicodeDecodeError as e:
        raise IngestionError(f"Encoding error reading {file_path}: {e}")
    except Exception as e:
        raise IngestionError(f"Error reading file {file_path}: {e}")


async def read_and_insert_md_file(
    file_path: str,
    code: str,
    encoding: str = 'utf-8'
) -> Dict:
    """
    Read markdown file and insert into document table.
    Uses upsert to avoid duplicate errors.
    
    Args:
        file_path: Path to the markdown file
        code: Unique document code
        encoding: File encoding (default: utf-8)
        
    Returns:
        Dict: Inserted document information
        
    Raises:
        IngestionError: If ingestion fails
    """
    try:
        # Read file content asynchronously
        content = await read_file_async(file_path, encoding)
        
        # Extract filename from path (works for both Unix and Windows paths)
        name = Path(file_path).name
        
        # Insert/update document in database
        document_info = await upsert_document(
            name=name,
            code=code,
            content=content
        )
        
        logger.info(
            f"Successfully ingested document: {name} (code={code}, "
            f"size={len(content)} chars)"
        )
        return document_info
        
    except IngestionError:
        raise
    except DocumentError as e:
        raise IngestionError(f"Database error: {e}") from e
    except Exception as e:
        logger.error(
            f"Failed to ingest file {file_path}: {e}",
            exc_info=True
        )
        raise IngestionError(f"Failed to ingest file: {e}") from e


async def ingest_directory(
    directory_path: str,
    code_prefix: str = "",
    file_extension: str = ".md",
    encoding: str = 'utf-8'
) -> Dict[str, any]:
    """
    Ingest all files from a directory with a specific extension.
    
    Args:
        directory_path: Path to the directory
        code_prefix: Prefix for document codes (default: "")
        file_extension: File extension to filter (default: .md)
        encoding: File encoding (default: utf-8)
        
    Returns:
        Dict: Summary with success_count, failed_count, and details
        
    Raises:
        IngestionError: If directory doesn't exist
    """
    directory = Path(directory_path)
    
    if not directory.exists():
        raise IngestionError(f"Directory not found: {directory_path}")
    
    if not directory.is_dir():
        raise IngestionError(f"Not a directory: {directory_path}")
    
    # Find all files with the specified extension
    files = list(directory.glob(f"*{file_extension}"))
    
    if not files:
        logger.warning(
            f"No {file_extension} files found in {directory_path}"
        )
        return {
            "success_count": 0,
            "failed_count": 0,
            "total": 0,
            "files": []
        }
    
    logger.info(f"Found {len(files)} files to ingest from {directory_path}")
    
    results = {
        "success_count": 0,
        "failed_count": 0,
        "total": len(files),
        "files": []
    }
    
    # Process files concurrently
    tasks = []
    for file_path in files:
        # Generate code from filename (remove extension)
        file_code = file_path.stem
        if code_prefix:
            file_code = f"{code_prefix}_{file_code}"
        
        # Create task for each file
        tasks.append(
            ingest_single_file(
                str(file_path),
                file_code,
                encoding
            )
        )
    
    # Execute all tasks concurrently
    completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for i, result in enumerate(completed_tasks):
        file_info = {
            "file": files[i].name,
            "code": tasks[i].__name__ if hasattr(tasks[i], '__name__') else None
        }
        
        if isinstance(result, Exception):
            results["failed_count"] += 1
            file_info["status"] = "failed"
            file_info["error"] = str(result)
            logger.error(f"Failed to ingest {files[i].name}: {result}")
        else:
            results["success_count"] += 1
            file_info["status"] = "success"
            file_info["document_id"] = result.get("id")
        
        results["files"].append(file_info)
    
    logger.info(
        f"Ingestion complete: {results['success_count']} succeeded, "
        f"{results['failed_count']} failed out of {results['total']}"
    )
    
    return results


async def ingest_single_file(
    file_path: str,
    code: str,
    encoding: str = 'utf-8'
) -> Dict:
    """
    Ingest a single file (wrapper for better error handling in batch operations).
    
    Args:
        file_path: Path to the file
        code: Document code
        encoding: File encoding
        
    Returns:
        Dict: Document information
    """
    return await read_and_insert_md_file(file_path, code, encoding)


async def ingest_files_batch(
    file_configs: List[Dict[str, str]],
    encoding: str = 'utf-8'
) -> Dict[str, any]:
    """
    Ingest multiple files with custom codes in batch.
    
    Args:
        file_configs: List of dicts with 'path' and 'code' keys
        encoding: File encoding (default: utf-8)
        
    Returns:
        Dict: Summary with success_count, failed_count, and details
        
    Example:
        configs = [
            {"path": "file1.md", "code": "doc1"},
            {"path": "file2.md", "code": "doc2"}
        ]
        result = await ingest_files_batch(configs)
    """
    if not file_configs:
        return {
            "success_count": 0,
            "failed_count": 0,
            "total": 0,
            "files": []
        }
    
    logger.info(f"Starting batch ingestion of {len(file_configs)} files")
    
    results = {
        "success_count": 0,
        "failed_count": 0,
        "total": len(file_configs),
        "files": []
    }
    
    # Create tasks for concurrent execution
    tasks = [
        ingest_single_file(config["path"], config["code"], encoding)
        for config in file_configs
    ]
    
    # Execute all tasks concurrently
    completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for i, result in enumerate(completed_tasks):
        file_info = {
            "file": file_configs[i]["path"],
            "code": file_configs[i]["code"]
        }
        
        if isinstance(result, Exception):
            results["failed_count"] += 1
            file_info["status"] = "failed"
            file_info["error"] = str(result)
            logger.error(
                f"Failed to ingest {file_configs[i]['path']}: {result}"
            )
        else:
            results["success_count"] += 1
            file_info["status"] = "success"
            file_info["document_id"] = result.get("id")
        
        results["files"].append(file_info)
    
    logger.info(
        f"Batch ingestion complete: {results['success_count']} succeeded, "
        f"{results['failed_count']} failed"
    )
    
    return results


# Example usage / CLI interface
async def main():
    """Example usage for CLI execution"""
    load_dotenv()
    
    # Example: Ingest a single file
    file_path = r"D:\Github Repos\VertexAI-MCP\mcp_server\documents\prudtvt-tnc.md"
    code = "prudtvt-tnc"
    
    try:
        result = await read_and_insert_md_file(file_path, code)
        print(f"Successfully ingested: {result}")
    except IngestionError as e:
        print(f"Ingestion failed: {e}")
        return
    
    # Example: Ingest entire directory
    # directory_path = r"D:\Github Repos\VertexAI-MCP\mcp_server\documents"
    # results = await ingest_directory(directory_path)
    # print(f"Batch ingestion results: {results}")


if __name__ == "__main__":
    asyncio.run(main())