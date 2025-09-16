# Insurance MCP System - Getting Started

This guide will help you set up and test the complete Insurance MCP (Model Context Protocol) system.

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │───▶│   MCP Client    │───▶│   MCP Server    │
│   (Port 3000)   │    │   (Port 8080)   │    │   (Port 8081)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                          │
                              ▼                          ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │  Chat History   │    │   Documents     │
                    │   Database      │    │   Database      │
                    └─────────────────┘    └─────────────────┘
```

## Quick Start with Docker

### 1. Start the entire system
```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

### 2. Verify services are running
```bash
# Check service status
docker-compose ps

# Check logs
docker-compose logs mcp-server
docker-compose logs mcp-client
```

### 3. Test the system
```bash
# Health checks
curl http://localhost:8080/health  # Client health
curl http://localhost:8081/health  # Server health (if exposed)

# Test document listing
curl http://localhost:8080/documents

# Test chat
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "test-123",
    "user_id": 1,
    "message": "Tôi muốn tìm hiểu về sản phẩm PruMax",
    "include_history": true
  }'
```

## Manual Setup (Development)

### 1. Install Dependencies

**MCP Server:**
```bash
cd mcp_server
pip install -r requirements.txt
```

**MCP Client:**
```bash
cd mcp_client
pip install -r requirements.txt
```

### 2. Database Setup
```bash
# Start PostgreSQL (using Docker)
docker run -d --name postgres \
  -e POSTGRES_DB=insurance_mcp \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  postgres:15-alpine

# Initialize database (from mcp_server directory)
python -c "from database import init_document_table; init_document_table()"
```

### 3. Start Services

**Terminal 1 - MCP Server:**
```bash
cd mcp_server
python sse_server.py --host 0.0.0.0 --port 8081
```

**Terminal 2 - MCP Client:**
```bash
cd mcp_client
python client_sse.py --host 0.0.0.0 --port 8080 --server-url http://localhost:8081
```

### 4. Test Connection

**Simple test (no FastAPI dependencies):**
```bash
cd mcp_client
python simple_test.py
```

**Full test suite:**
```bash
cd mcp_client
python test_connection.py
```

## API Endpoints

### MCP Client API (Port 8080)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check and system status |
| GET | `/documents` | List all insurance documents |
| GET | `/documents/{code}` | Get specific document content |
| POST | `/chat` | Process insurance inquiry |
| GET | `/chat/{thread_id}/history` | Get chat history |
| GET | `/tools` | List available MCP tools |
| POST | `/tools/call` | Direct tool calling |

### Example API Usage

**Get available documents:**
```bash
curl http://localhost:8080/documents
```

**Chat with the system:**
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "user-session-123",
    "user_id": 1,
    "message": "So sánh giữa PruMax và Education Saver",
    "include_history": true
  }'
```

**Get chat history:**
```bash
curl http://localhost:8080/chat/user-session-123/history?limit=5
```

## Configuration

### Environment Variables

**MCP Client (.env):**
```env
MCP_SERVER_URL=http://localhost:8081
CLIENT_HOST=0.0.0.0
CLIENT_PORT=8080
DB_HOST=localhost
DB_PORT=5432
DB_NAME=insurance_mcp
DB_USER=postgres
DB_PASSWORD=your_password
```

### Product Codes

The system recognizes these insurance product codes:
- `pru-edu-saver` - Education Saver main document
- `pru-edu-saver-faq` - Education Saver FAQ
- `pru-edu-saver-tnc` - Education Saver Terms & Conditions
- `prumax` - PruMax main document
- `prumax-faq` - PruMax FAQ
- `prumax-tnc` - PruMax Terms & Conditions

## Troubleshooting

### Common Issues

1. **Connection refused to MCP server**
   - Check server is running on port 8081
   - Verify firewall/network settings
   - Check Docker network connectivity

2. **Database connection errors**
   - Ensure PostgreSQL is running
   - Verify database credentials
   - Check database initialization

3. **Import errors**
   - Install requirements: `pip install -r requirements.txt`
   - Check Python path configuration

4. **Docker build issues**
   - Update Docker and Docker Compose
   - Clear build cache: `docker-compose build --no-cache`

### Debug Commands

```bash
# Check MCP server tools
curl -X POST http://localhost:8080/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "list_documents", "arguments": {}}'

# Direct server health (if accessible)
curl http://localhost:8081/sse

# Database connection test
python -c "from database import get_db_connection; print('DB OK' if get_db_connection() else 'DB Error')"
```

## Next Steps

1. **Frontend Integration**: Connect your React/Vue/Angular frontend to `http://localhost:8080`
2. **LLM Integration**: Add Vertex AI or other LLM for intelligent responses
3. **Authentication**: Implement user authentication and authorization
4. **Monitoring**: Add logging, metrics, and monitoring
5. **Production**: Configure for production deployment with proper security

## Support

- Check logs: `docker-compose logs [service-name]`
- Run tests: `python test_connection.py`
- Simple connectivity: `python simple_test.py`