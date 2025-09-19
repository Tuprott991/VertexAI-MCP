import sys
import os
from dotenv import load_dotenv
from psycopg.rows import dict_row
from datetime import datetime
from typing import List, Dict
from uuid import uuid4

# Add parent directory to path for relative imports when running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connect_db import get_db_connection

def init_document_table():
    # Khởi tạo bảng document trong database nếu chưa tồn tại
    # 4 trường: ID là uuid, mã tài liệu, tên tài liệu, nội dung, thời gian tạo
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Enable UUID extension if not exists
            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
            
            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS document (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    code VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL, 
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index if not exists
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_name 
                ON document(name)
            """)
        conn.commit()


def insert_document(name: str, code: str, content: str) -> Dict:
    """
    Chèn một tài liệu mới vào bảng document
    
    Args:
        name (str): Tên tài liệu
        content (str): Nội dung tài liệu
        
    Returns:
        Dict: Thông tin tài liệu vừa được chèn
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO document (name, code, content) VALUES (%s, %s, %s) RETURNING id::text, code, name, created_at",
                (name, code, content)
            )
            result = cur.fetchone()
            conn.commit()
            return result

def get_list_of_documents() -> List[Dict]:
    """
    Lấy danh sách tất cả các tài liệu từ bảng document
    
    Returns:
        List[Dict]: Danh sách tên các tài liệu đang có trong hệ thống
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, code, name, created_at FROM document ORDER BY created_at DESC"
            )
            return cur.fetchall()

# Lấy document theo mã tài liệu "vd: pru360"
def get_document_by_code(code: str) -> Dict:
    """
    Lấy thông tin tài liệu theo mã tài liệu
    
    Args:
        code (str): Mã tài liệu
        
    Returns:
        Dict: Thông tin tài liệu
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id::text, code, name, content, created_at FROM document WHERE code = %s",
                (code,)
            )
            return cur.fetchone()

if __name__ == "__main__":
    init_document_table()