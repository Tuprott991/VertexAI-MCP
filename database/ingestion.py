from database.connect_db import get_db_connection
from dotenv import load_dotenv
from psycopg.rows import dict_row
from datetime import datetime
from typing import List, Dict


import sys
import os

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import insert_document

def read_and_insert_md_file(file_path: str, code: str):
    """
    Đọc nội dung từ file .md và chèn vào bảng document
    
    Args:
        file_path (str): Đường dẫn tới file .md
        code (str): Mã tài liệu duy nhất
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            name = file_path.split('/')[-1]  # Lấy tên file từ đường dẫn
            
            # Chèn vào bảng document
            document_info = insert_document(name=name, code=code, content=content)
            print(f"Inserted document: {document_info}")
    except Exception as e:
        print(f"Error reading or inserting document: {e}")
        raise

if __name__ == "__main__":
    load_dotenv()  # Load biến môi trường từ file .env nếu cần
    # Ví dụ sử dụng
    # Read folder and insert all .md files
    import os
    file_path = r'D:/Github Repos/VertexAI-MCP/mcp_server/documents/pru-edu-saver-faq.md'  # Thay đổi đường dẫn tới thư mục chứa file .md

    read_and_insert_md_file(file_path, code="pru-edu-saver-faq")