"""
Production-ready async chat history management with proper error handling.

Features:
- Async database operations with transaction support
- Comprehensive error handling and logging
- Type hints for better code safety
- Connection pooling from connect_db module
- Proper exception handling and rollback
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from uuid import uuid4

from database.connect_db import (
    get_db_connection,
    get_db_transaction,
    DatabaseError
)

logger = logging.getLogger(__name__)


class ChatHistoryError(Exception):
    """Base exception for chat history errors"""
    pass


async def init_chat_history_table() -> None:
    """
    Initialize the message table in database if it doesn't exist.
    
    Creates table structure for storing chat history:
    - id: UUID primary key
    - thread_id: Conversation thread identifier
    - question: User's question
    - answer: Chatbot's response
    - created_at: Timestamp
    
    Raises:
        ChatHistoryError: If table creation fails
    """
    try:
        async with get_db_transaction() as conn:
            # Enable UUID extension if not exists
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            
            # Create message table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS message (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    thread_id VARCHAR(255) NOT NULL, 
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster thread_id lookups
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_thread_id 
                ON message(thread_id)
            """)
            
            # Create index for created_at for efficient sorting
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_created_at 
                ON message(created_at DESC)
            """)
            
        logger.info("Chat history table initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize chat history table: {e}", exc_info=True)
        raise ChatHistoryError(f"Failed to initialize chat history table: {e}") from e


async def create_thread_id_for_user(user_id: int) -> str:
    """
    Create a new conversation thread ID for a user.
    
    Args:
        user_id: The user's ID
        
    Returns:
        str: The newly created thread ID (UUID)
        
    Raises:
        ChatHistoryError: If thread creation fails
    """
    thread_id = str(uuid4())
    
    try:
        async with get_db_transaction() as conn:
            # Append the new thread_id to user's threads array
            await conn.execute(
                """
                UPDATE user_info
                SET threads = array_append(threads, $1)
                WHERE id = $2
                """,
                thread_id, user_id
            )
            
        logger.info(f"Created thread ID: {thread_id} for user: {user_id}")
        return thread_id
        
    except Exception as e:
        logger.error(
            f"Failed to create thread ID for user {user_id}: {e}",
            exc_info=True
        )
        raise ChatHistoryError(f"Failed to create thread ID: {e}") from e


async def get_thread_ids_for_user(user_id: int) -> List[str]:
    """
    Get list of conversation thread IDs for a user.
    
    Args:
        user_id: The user's ID
        
    Returns:
        List[str]: List of unique thread IDs
        
    Raises:
        ChatHistoryError: If retrieval fails
    """
    try:
        async with get_db_connection() as conn:
            result = await conn.fetchrow(
                "SELECT threads FROM user_info WHERE id = $1",
                user_id
            )
            
            if result and result['threads']:
                # Remove duplicates and return unique thread IDs
                return list(set(result['threads']))
            return []
            
    except Exception as e:
        logger.error(
            f"Failed to get thread IDs for user {user_id}: {e}",
            exc_info=True
        )
        raise ChatHistoryError(f"Failed to get thread IDs: {e}") from e


async def save_chat_history(
    user_id: int,
    thread_id: str,
    question: str,
    answer: str
) -> str:
    """
    Save chat history to database within a transaction.
    
    Args:
        user_id: The user's ID
        thread_id: The conversation thread ID
        question: User's question
        answer: Chatbot's response
        
    Returns:
        str: The message ID (UUID) of the saved chat
        
    Raises:
        ChatHistoryError: If save operation fails
    """
    try:
        async with get_db_transaction() as conn:
            # Insert chat history into message table
            result = await conn.fetchrow(
                """
                INSERT INTO message (thread_id, question, answer)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                thread_id, question, answer
            )
            
            message_id = str(result['id'])
            
            # Update user_info to include thread_id if not already present
            await conn.execute(
                """
                UPDATE user_info
                SET threads = CASE
                    WHEN $1 = ANY(threads) THEN threads
                    ELSE array_append(threads, $1)
                END 
                WHERE id = $2
                """,
                thread_id, user_id
            )
            
        logger.info(
            f"Saved chat history: message_id={message_id}, "
            f"thread_id={thread_id}, user_id={user_id}"
        )
        return message_id
        
    except Exception as e:
        logger.error(
            f"Failed to save chat history for user {user_id}: {e}",
            exc_info=True
        )
        raise ChatHistoryError(f"Failed to save chat history: {e}") from e


async def get_recent_chat_history(
    thread_id: str,
    limit: int = 10,
    offset: int = 0
) -> List[Dict]:
    """
    Get recent chat history for a conversation thread.
    
    Args:
        thread_id: The conversation thread ID
        limit: Maximum number of messages to retrieve (default: 10)
        offset: Number of messages to skip (default: 0)
        
    Returns:
        List[Dict]: List of chat messages with id, thread_id, question, answer, created_at
        
    Raises:
        ChatHistoryError: If retrieval fails
    """
    if limit <= 0:
        raise ValueError("Limit must be positive")
    if offset < 0:
        raise ValueError("Offset must be non-negative")
        
    try:
        async with get_db_connection() as conn:
            results = await conn.fetch(
                """
                SELECT 
                    id::text,
                    thread_id,
                    question,
                    answer,
                    created_at
                FROM message 
                WHERE thread_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2 OFFSET $3
                """,
                thread_id, limit, offset
            )
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(
            f"Failed to get chat history for thread {thread_id}: {e}",
            exc_info=True
        )
        raise ChatHistoryError(f"Failed to get chat history: {e}") from e


async def get_chat_message_by_id(message_id: str) -> Optional[Dict]:
    """
    Get a specific chat message by its ID.
    
    Args:
        message_id: The message UUID
        
    Returns:
        Optional[Dict]: Message details or None if not found
        
    Raises:
        ChatHistoryError: If retrieval fails
    """
    try:
        async with get_db_connection() as conn:
            result = await conn.fetchrow(
                """
                SELECT 
                    id::text,
                    thread_id,
                    question,
                    answer,
                    created_at
                FROM message 
                WHERE id = $1::uuid
                """,
                message_id
            )
            
            return dict(result) if result else None
            
    except Exception as e:
        logger.error(
            f"Failed to get message {message_id}: {e}",
            exc_info=True
        )
        raise ChatHistoryError(f"Failed to get message: {e}") from e


async def delete_chat_message(message_id: str) -> bool:
    """
    Delete a specific chat message.
    
    Args:
        message_id: The message UUID to delete
        
    Returns:
        bool: True if deleted, False if not found
        
    Raises:
        ChatHistoryError: If deletion fails
    """
    try:
        async with get_db_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM message WHERE id = $1::uuid",
                message_id
            )
            
            deleted = result.split()[-1] == "1"
            if deleted:
                logger.info(f"Deleted message: {message_id}")
            return deleted
            
    except Exception as e:
        logger.error(
            f"Failed to delete message {message_id}: {e}",
            exc_info=True
        )
        raise ChatHistoryError(f"Failed to delete message: {e}") from e


async def delete_thread_history(thread_id: str) -> int:
    """
    Delete all messages in a conversation thread.
    
    Args:
        thread_id: The conversation thread ID
        
    Returns:
        int: Number of messages deleted
        
    Raises:
        ChatHistoryError: If deletion fails
    """
    try:
        async with get_db_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM message WHERE thread_id = $1",
                thread_id
            )
            
            count = int(result.split()[-1])
            logger.info(f"Deleted {count} messages from thread: {thread_id}")
            return count
            
    except Exception as e:
        logger.error(
            f"Failed to delete thread {thread_id}: {e}",
            exc_info=True
        )
        raise ChatHistoryError(f"Failed to delete thread: {e}") from e


def format_chat_history(chat_history: List[Dict]) -> List[Dict[str, str]]:
    """
    Format chat history for conversation context.
    
    Args:
        chat_history: List of chat message dictionaries
        
    Returns:
        List[Dict[str, str]]: Formatted messages with role and content
    """
    formatted_history = []
    
    # Reverse to get chronological order (oldest first)
    for msg in reversed(chat_history):
        formatted_history.extend([
            {"role": "human", "content": msg["question"]},
            {"role": "assistant", "content": msg["answer"]}
        ])
        
    return formatted_history 
