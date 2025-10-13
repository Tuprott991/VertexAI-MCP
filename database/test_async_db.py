"""
Test suite for the async database module.
Run with: python -m pytest database/test_async_db.py -v
Or: python database/test_async_db.py
"""

import asyncio
import pytest
import logging
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO)

# Test imports
from database import (
    # Connection
    get_connection_pool,
    close_connection_pool,
    health_check,
    
    # Tables
    init_chat_history_table,
    init_document_table,
    
    # Chat operations
    create_thread_id_for_user,
    save_chat_history,
    get_recent_chat_history,
    get_chat_message_by_id,
    delete_chat_message,
    format_chat_history,
    
    # Document operations
    insert_document,
    upsert_document,
    get_document_by_code,
    get_list_of_documents,
    search_documents,
    update_document_content,
    delete_document,
    get_document_count,
    
    # Ingestion
    read_and_insert_md_file,
    
    # Exceptions
    DatabaseError,
    DocumentError,
    ChatHistoryError,
)


class TestConnectionPool:
    """Test connection pool functionality"""
    
    async def test_connection_pool_creation(self):
        """Test that connection pool is created successfully"""
        pool = await get_connection_pool()
        assert pool is not None
        assert pool.get_size() > 0
        print("✓ Connection pool created")
    
    async def test_health_check(self):
        """Test database health check"""
        is_healthy = await health_check()
        assert is_healthy is True
        print("✓ Health check passed")


class TestDocumentOperations:
    """Test document CRUD operations"""
    
    async def test_init_document_table(self):
        """Test document table initialization"""
        await init_document_table()
        print("✓ Document table initialized")
    
    async def test_insert_document(self):
        """Test inserting a new document"""
        code = f"test_doc_{uuid4().hex[:8]}"
        doc = await insert_document(
            name="Test Document",
            code=code,
            content="This is test content"
        )
        assert doc is not None
        assert doc['code'] == code
        assert 'id' in doc
        print(f"✓ Document inserted: {code}")
        return code
    
    async def test_upsert_document(self):
        """Test upsert (insert or update) document"""
        code = f"test_upsert_{uuid4().hex[:8]}"
        
        # First insert
        doc1 = await upsert_document(
            name="Original",
            code=code,
            content="Original content"
        )
        assert doc1['name'] == "Original"
        
        # Update via upsert
        doc2 = await upsert_document(
            name="Updated",
            code=code,
            content="Updated content"
        )
        assert doc2['name'] == "Updated"
        assert doc2['id'] == doc1['id']  # Same ID
        print(f"✓ Document upserted: {code}")
    
    async def test_get_document_by_code(self):
        """Test retrieving document by code"""
        code = f"test_get_{uuid4().hex[:8]}"
        
        # Insert first
        await insert_document(
            name="Get Test",
            code=code,
            content="Content"
        )
        
        # Retrieve
        doc = await get_document_by_code(code)
        assert doc is not None
        assert doc['code'] == code
        assert doc['content'] == "Content"
        print(f"✓ Document retrieved: {code}")
    
    async def test_get_list_of_documents(self):
        """Test getting list of documents"""
        documents = await get_list_of_documents(limit=10)
        assert isinstance(documents, list)
        print(f"✓ Retrieved {len(documents)} documents")
    
    async def test_search_documents(self):
        """Test document search"""
        code = f"test_search_{uuid4().hex[:8]}"
        search_term = "searchable_unique_term"
        
        # Insert document with searchable content
        await insert_document(
            name="Searchable Doc",
            code=code,
            content=f"This document contains {search_term}"
        )
        
        # Search
        results = await search_documents(search_term, limit=10)
        assert len(results) > 0
        assert any(doc['code'] == code for doc in results)
        print(f"✓ Document search works")
    
    async def test_update_document_content(self):
        """Test updating document content"""
        code = f"test_update_{uuid4().hex[:8]}"
        
        # Insert
        await insert_document(
            name="Update Test",
            code=code,
            content="Original"
        )
        
        # Update
        updated = await update_document_content(code, "Updated content")
        assert updated is True
        
        # Verify
        doc = await get_document_by_code(code)
        assert doc['content'] == "Updated content"
        print(f"✓ Document updated: {code}")
    
    async def test_delete_document(self):
        """Test deleting a document"""
        code = f"test_delete_{uuid4().hex[:8]}"
        
        # Insert
        await insert_document(
            name="Delete Test",
            code=code,
            content="To be deleted"
        )
        
        # Delete
        deleted = await delete_document(code)
        assert deleted is True
        
        # Verify
        doc = await get_document_by_code(code)
        assert doc is None
        print(f"✓ Document deleted: {code}")
    
    async def test_get_document_count(self):
        """Test getting total document count"""
        count = await get_document_count()
        assert isinstance(count, int)
        assert count >= 0
        print(f"✓ Document count: {count}")


# class TestChatHistoryOperations:
#     """Test chat history CRUD operations"""
    
#     async def test_init_chat_history_table(self):
#         """Test chat history table initialization"""
#         await init_chat_history_table()
#         print("✓ Chat history table initialized")
    
#     async def test_save_and_retrieve_chat(self):
#         """Test saving and retrieving chat history"""
#         user_id = 1
#         thread_id = f"test_thread_{uuid4().hex[:8]}"
        
#         # Save chat
#         msg_id = await save_chat_history(
#             user_id=user_id,
#             thread_id=thread_id,
#             question="What is async programming?",
#             answer="Async programming allows concurrent operations."
#         )
#         assert msg_id is not None
#         print(f"✓ Chat saved: {msg_id}")
        
#         # Retrieve
#         history = await get_recent_chat_history(thread_id, limit=5)
#         assert len(history) > 0
#         assert history[0]['question'] == "What is async programming?"
#         print(f"✓ Chat history retrieved")
    
#     async def test_get_chat_message_by_id(self):
#         """Test retrieving specific chat message"""
#         user_id = 1
#         thread_id = f"test_msg_{uuid4().hex[:8]}"
        
#         # Save
#         msg_id = await save_chat_history(
#             user_id=user_id,
#             thread_id=thread_id,
#             question="Test question",
#             answer="Test answer"
#         )
        
#         # Retrieve by ID
#         message = await get_chat_message_by_id(msg_id)
#         assert message is not None
#         assert message['question'] == "Test question"
#         print(f"✓ Message retrieved by ID")
    
#     async def test_format_chat_history(self):
#         """Test formatting chat history"""
#         user_id = 1
#         thread_id = f"test_format_{uuid4().hex[:8]}"
        
#         # Save multiple messages
#         await save_chat_history(user_id, thread_id, "Q1", "A1")
#         await save_chat_history(user_id, thread_id, "Q2", "A2")
        
#         # Get and format
#         history = await get_recent_chat_history(thread_id, limit=10)
#         formatted = format_chat_history(history)
        
#         assert isinstance(formatted, list)
#         assert len(formatted) >= 4  # 2 Q&A pairs = 4 messages
#         print(f"✓ Chat history formatted")
    
#     async def test_delete_chat_message(self):
#         """Test deleting a chat message"""
#         user_id = 1
#         thread_id = f"test_delete_{uuid4().hex[:8]}"
        
#         # Save
#         msg_id = await save_chat_history(
#             user_id=user_id,
#             thread_id=thread_id,
#             question="Delete me",
#             answer="Will be deleted"
#         )
        
#         # Delete
#         deleted = await delete_chat_message(msg_id)
#         assert deleted is True
        
#         # Verify
#         message = await get_chat_message_by_id(msg_id)
#         assert message is None
#         print(f"✓ Message deleted")


class TestConcurrentOperations:
    """Test concurrent database operations"""
    
    async def test_concurrent_inserts(self):
        """Test multiple concurrent document inserts"""
        tasks = []
        for i in range(10):
            code = f"concurrent_{uuid4().hex[:8]}"
            tasks.append(
                insert_document(
                    name=f"Concurrent Doc {i}",
                    code=code,
                    content=f"Content {i}"
                )
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check all succeeded
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 10
        print(f"✓ {len(successful)} concurrent inserts completed")
    
    async def test_concurrent_reads(self):
        """Test multiple concurrent document reads"""
        # First, ensure we have documents
        codes = []
        for i in range(5):
            code = f"read_test_{uuid4().hex[:8]}"
            await insert_document(
                name=f"Read Test {i}",
                code=code,
                content=f"Content {i}"
            )
            codes.append(code)
        
        # Concurrent reads
        tasks = [get_document_by_code(code) for code in codes]
        results = await asyncio.gather(*tasks)
        
        assert all(doc is not None for doc in results)
        print(f"✓ {len(results)} concurrent reads completed")


async def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*60)
    print("ASYNC DATABASE MODULE TEST SUITE")
    print("="*60 + "\n")
    
    try:
        # Connection tests
        print("1. Testing Connection Pool...")
        conn_tests = TestConnectionPool()
        await conn_tests.test_connection_pool_creation()
        await conn_tests.test_health_check()
        
        # Document tests
        print("\n2. Testing Document Operations...")
        doc_tests = TestDocumentOperations()
        await doc_tests.test_init_document_table()
        await doc_tests.test_insert_document()
        await doc_tests.test_upsert_document()
        await doc_tests.test_get_document_by_code()
        await doc_tests.test_get_list_of_documents()
        await doc_tests.test_search_documents()
        await doc_tests.test_update_document_content()
        await doc_tests.test_delete_document()
        await doc_tests.test_get_document_count()
        
        # Concurrent operations
        print("\n3. Testing Concurrent Operations...")
        concurrent_tests = TestConcurrentOperations()
        await concurrent_tests.test_concurrent_inserts()
        await concurrent_tests.test_concurrent_reads()
        
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        await close_connection_pool()
        print("Connection pool closed")
    
    return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
