"""
Production-ready async document management with proper error handling.

Features:
- Async database operations with transaction support
- Comprehensive error handling and logging
- Type hints for better code safety
- Connection pooling from connect_db module
- Upsert operations for idempotent inserts
- Proper exception handling and rollback
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional

from database.connect_db import (
    get_db_connection,
    get_db_transaction,
    DatabaseError
)

logger = logging.getLogger(__name__)


class DocumentError(Exception):
    """Base exception for document errors"""
    pass


async def init_document_table() -> None:
    """
    Initialize the document table in database if it doesn't exist.
    
    Creates table structure for storing documents:
    - id: UUID primary key
    - code: Unique document code (e.g., "pru360")
    - name: Document name
    - content: Document content (text)
    - created_at: Timestamp with timezone
    - updated_at: Timestamp with timezone for tracking updates
    
    Raises:
        DocumentError: If table creation fails
    """
    try:
        async with get_db_transaction() as conn:
            # Enable UUID extension if not exists
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            
            # Create document table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS document (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    code VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL, 
                    content TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for document name searches
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_name 
                ON document(name)
            """)
            
            # Create index for created_at for efficient sorting
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_created_at 
                ON document(created_at DESC)
            """)
            
            # Create GIN index for full-text search on content (optional but recommended)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_content_search 
                ON document USING gin(to_tsvector('english', content))
            """)
            
        logger.info("Document table initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize document table: {e}", exc_info=True)
        raise DocumentError(f"Failed to initialize document table: {e}") from e


async def insert_document(name: str, code: str, content: str) -> Dict:
    """
    Insert a new document into the database.
    
    Args:
        name: Document name
        code: Unique document code
        content: Document content
        
    Returns:
        Dict: Document information including id, code, name, created_at
        
    Raises:
        DocumentError: If insertion fails (e.g., duplicate code)
    """
    try:
        async with get_db_transaction() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO document (name, code, content)
                VALUES ($1, $2, $3)
                RETURNING id, code, name, created_at
                """,
                name, code, content
            )
            
            doc = dict(result)
            doc['id'] = str(doc['id'])
            
        logger.info(f"Inserted document: code={code}, name={name}")
        return doc
        
    except Exception as e:
        logger.error(
            f"Failed to insert document (code={code}): {e}",
            exc_info=True
        )
        raise DocumentError(f"Failed to insert document: {e}") from e


async def upsert_document(name: str, code: str, content: str) -> Dict:
    """
    Insert or update a document (upsert operation).
    If a document with the same code exists, update it; otherwise insert new.
    
    Args:
        name: Document name
        code: Unique document code
        content: Document content
        
    Returns:
        Dict: Document information including id, code, name, created_at, updated_at
        
    Raises:
        DocumentError: If operation fails
    """
    try:
        async with get_db_transaction() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO document (name, code, content, created_at, updated_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (code) 
                DO UPDATE SET 
                    name = EXCLUDED.name,
                    content = EXCLUDED.content,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, code, name, created_at, updated_at
                """,
                name, code, content
            )
            
            doc = dict(result)
            doc['id'] = str(doc['id'])
            
        logger.info(f"Upserted document: code={code}, name={name}")
        return doc
        
    except Exception as e:
        logger.error(
            f"Failed to upsert document (code={code}): {e}",
            exc_info=True
        )
        raise DocumentError(f"Failed to upsert document: {e}") from e


async def get_list_of_documents(
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """
    Get list of all documents (without content for performance).
    
    Args:
        limit: Maximum number of documents to retrieve (default: 100)
        offset: Number of documents to skip (default: 0)
        
    Returns:
        List[Dict]: List of documents with id, code, name, created_at
        
    Raises:
        DocumentError: If retrieval fails
    """
    if limit <= 0:
        raise ValueError("Limit must be positive")
    if offset < 0:
        raise ValueError("Offset must be non-negative")
        
    try:
        async with get_db_connection() as conn:
            results = await conn.fetch(
                """
                SELECT id, code, name, created_at
                FROM document 
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit, offset
            )
            
            documents = []
            for row in results:
                doc = dict(row)
                doc['id'] = str(doc['id'])
                documents.append(doc)
                
            return documents
            
    except Exception as e:
        logger.error(f"Failed to get document list: {e}", exc_info=True)
        raise DocumentError(f"Failed to get document list: {e}") from e


async def get_document_by_code(code: str) -> Optional[Dict]:
    """
    Get document information by document code.
    
    Args:
        code: Document code (e.g., "pru360")
        
    Returns:
        Optional[Dict]: Document information or None if not found
        
    Raises:
        DocumentError: If retrieval fails
    """
    try:
        async with get_db_connection() as conn:
            result = await conn.fetchrow(
                """
                SELECT id, code, name, content, created_at, updated_at
                FROM document 
                WHERE code = $1
                """,
                code
            )
            
            if result:
                doc = dict(result)
                doc['id'] = str(doc['id'])
                return doc
            return None
            
    except Exception as e:
        logger.error(
            f"Failed to get document by code ({code}): {e}",
            exc_info=True
        )
        raise DocumentError(f"Failed to get document: {e}") from e


async def get_document_by_id(document_id: str) -> Optional[Dict]:
    """
    Get document information by document ID.
    
    Args:
        document_id: Document UUID
        
    Returns:
        Optional[Dict]: Document information or None if not found
        
    Raises:
        DocumentError: If retrieval fails
    """
    try:
        async with get_db_connection() as conn:
            result = await conn.fetchrow(
                """
                SELECT id, code, name, content, created_at, updated_at
                FROM document 
                WHERE id = $1::uuid
                """,
                document_id
            )
            
            if result:
                doc = dict(result)
                doc['id'] = str(doc['id'])
                return doc
            return None
            
    except Exception as e:
        logger.error(
            f"Failed to get document by ID ({document_id}): {e}",
            exc_info=True
        )
        raise DocumentError(f"Failed to get document: {e}") from e


async def search_documents(search_term: str, limit: int = 50) -> List[Dict]:
    """
    Search documents by name or content using full-text search.
    
    Args:
        search_term: Search term to look for
        limit: Maximum number of results (default: 50)
        
    Returns:
        List[Dict]: List of matching documents
        
    Raises:
        DocumentError: If search fails
    """
    if limit <= 0:
        raise ValueError("Limit must be positive")
        
    try:
        async with get_db_connection() as conn:
            results = await conn.fetch(
                """
                SELECT id, code, name, created_at,
                       ts_rank(to_tsvector('english', content), 
                               plainto_tsquery('english', $1)) as rank
                FROM document
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                   OR name ILIKE $2
                ORDER BY rank DESC, created_at DESC
                LIMIT $3
                """,
                search_term, f"%{search_term}%", limit
            )
            
            documents = []
            for row in results:
                doc = dict(row)
                doc['id'] = str(doc['id'])
                del doc['rank']  # Remove rank from result
                documents.append(doc)
                
            return documents
            
    except Exception as e:
        logger.error(
            f"Failed to search documents (term={search_term}): {e}",
            exc_info=True
        )
        raise DocumentError(f"Failed to search documents: {e}") from e


async def update_document_content(code: str, content: str) -> bool:
    """
    Update document content by code.
    
    Args:
        code: Document code
        content: New content
        
    Returns:
        bool: True if updated, False if document not found
        
    Raises:
        DocumentError: If update fails
    """
    try:
        async with get_db_transaction() as conn:
            result = await conn.execute(
                """
                UPDATE document 
                SET content = $1, updated_at = CURRENT_TIMESTAMP
                WHERE code = $2
                """,
                content, code
            )
            
            updated = result.split()[-1] == "1"
            if updated:
                logger.info(f"Updated document content: code={code}")
            return updated
            
    except Exception as e:
        logger.error(
            f"Failed to update document content (code={code}): {e}",
            exc_info=True
        )
        raise DocumentError(f"Failed to update document: {e}") from e


async def delete_document(code: str) -> bool:
    """
    Delete a document by code.
    
    Args:
        code: Document code to delete
        
    Returns:
        bool: True if deleted, False if not found
        
    Raises:
        DocumentError: If deletion fails
    """
    try:
        async with get_db_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM document WHERE code = $1",
                code
            )
            
            deleted = result.split()[-1] == "1"
            if deleted:
                logger.info(f"Deleted document: code={code}")
            return deleted
            
    except Exception as e:
        logger.error(
            f"Failed to delete document (code={code}): {e}",
            exc_info=True
        )
        raise DocumentError(f"Failed to delete document: {e}") from e


async def get_document_count() -> int:
    """
    Get total count of documents in the database.
    
    Returns:
        int: Total number of documents
        
    Raises:
        DocumentError: If count fails
    """
    try:
        async with get_db_connection() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM document")
            return count
            
    except Exception as e:
        logger.error(f"Failed to count documents: {e}", exc_info=True)
        raise DocumentError(f"Failed to count documents: {e}") from e