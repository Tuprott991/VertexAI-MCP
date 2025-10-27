"""
Production-ready async database module for VertexAI-MCP.

This module provides async database operations with:
- Connection pooling and management
- Chat history management
- Document management
- File ingestion
- Transaction support
- Comprehensive error handling
"""

# Connection management
from database.connect_db import (
    get_db_connection,
    get_db_transaction,
    get_connection_pool,
    close_connection_pool,
    health_check,
    execute_with_retry,
    DatabaseError,
    ConnectionPoolError
)

# Chat history operations
from database.chat_history import (
    init_chat_history_table,
    create_thread_id_for_user,
    get_thread_ids_for_user,
    save_chat_history,
    get_recent_chat_history,
    get_chat_message_by_id,
    delete_chat_message,
    delete_thread_history,
    format_chat_history,
    ChatHistoryError
)

# Document operations
from database.document import (
    init_document_table,
    insert_document,
    upsert_document,
    get_list_of_documents,
    get_document_by_code,
    get_document_by_id,
    search_documents,
    update_document_content,
    delete_document,
    get_document_count,
    DocumentError
)

# Ingestion operations
from database.ingestion import (
    read_and_insert_md_file,
    ingest_directory,
    ingest_files_batch,
    IngestionError
)

from database.customer_data import (
    add_customer,
    get_customer,
    update_customer,
    delete_customer,
    CustomerDataError
)

__all__ = [
    # Connection management
    "get_db_connection",
    "get_db_transaction",
    "get_connection_pool",
    "close_connection_pool",
    "health_check",
    "execute_with_retry",
    "DatabaseError",
    "ConnectionPoolError",
    
    # Chat history
    "init_chat_history_table",
    "create_thread_id_for_user",
    "get_thread_ids_for_user",
    "save_chat_history",
    "get_recent_chat_history",
    "get_chat_message_by_id",
    "delete_chat_message",
    "delete_thread_history",
    "format_chat_history",
    "ChatHistoryError",
    
    # Document operations
    "init_document_table",
    "insert_document",
    "upsert_document",
    "get_list_of_documents",
    "get_document_by_code",
    "get_document_by_id",
    "search_documents",
    "update_document_content",
    "delete_document",
    "get_document_count",
    "DocumentError",
    
    # Ingestion
    "read_and_insert_md_file",
    "ingest_directory",
    "ingest_files_batch",
    "IngestionError",

    # Customer data
    "add_customer",
    "get_customer",
    "update_customer",
    "delete_customer",
    "CustomerDataError",
]

__version__ = "2.0.0"
__author__ = "VertexAI-MCP Team"