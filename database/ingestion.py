from database.connect_db import get_db_connection
from dotenv import load_dotenv
from psycopg.rows import dict_row
from datetime import datetime
from typing import List, Dict
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
            document_info = insert_document(name, content)
            print(f"Inserted document: {document_info}")
    except Exception as e:
        print(f"Error reading or inserting document: {e}")
        raise

if __name__ == "__main__":
    load_dotenv()  # Load biến môi trường từ file .env nếu cần
    # Ví dụ sử dụng
    # Read folder and insert all .md files
    import os
    folder_path = r'D:/Github Repos/VertexAI-MCP/mcp_server/documents'  # Thay đổi đường dẫn tới thư mục chứa file .md

    for filename in os.listdir(folder_path):
        if filename.endswith('.md'):
            file_path = os.path.join(folder_path, filename)
            code = filename[:-3]  # Lấy mã tài liệu từ tên file (bỏ đuôi .md)
            read_and_insert_md_file(file_path, code)