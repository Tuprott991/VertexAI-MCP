# Cloud Run Deployment Guide for MCP Server

## Prerequisites
- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed locally (optional for local testing)

## CORS Configuration

The server now includes CORS middleware to allow cross-origin requests from browser-based agents. 

### Production Security Recommendations

**Important**: The current configuration uses `allow_origins=["*"]` which allows all origins. For production, you should:

1. **Restrict to specific origins**:
```python
allow_origins=[
    "https://your-frontend.netlify.app",
    "https://your-custom-domain.com",
    "http://localhost:5173",  # For local development
]
```

2. **Update in `mcp_server/sse_server.py`**:
```python
# Add CORS middleware to allow cross-origin requests from browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGINS", "*").split(",")],  # Read from env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

3. **Set environment variable in Cloud Run**:
```bash
gcloud run services update mcp-sse-server \
    --set-env-vars="ALLOWED_ORIGINS=https://your-frontend.netlify.app,http://localhost:5173"
```

## Deployment Steps

### 1. Build and Push Docker Image

```bash
# Set your project ID
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1

# Configure Docker to use gcloud as credential helper
gcloud auth configure-docker

# Build the image
docker build -t gcr.io/$PROJECT_ID/mcp-sse-server:latest .

# Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/mcp-sse-server:latest
```

### 2. Deploy to Cloud Run

```bash
gcloud run deploy mcp-sse-server \
    --image gcr.io/$PROJECT_ID/mcp-sse-server:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300s \
    --max-instances 10 \
    --set-env-vars="ALLOWED_ORIGINS=*"
```

### 3. Deploy with Database Connection (Cloud SQL)

If using Cloud SQL for the database tools:

```bash
gcloud run deploy mcp-sse-server \
    --image gcr.io/$PROJECT_ID/mcp-sse-server:latest \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300s \
    --max-instances 10 \
    --add-cloudsql-instances=$PROJECT_ID:$REGION:your-instance-name \
    --set-env-vars="DB_HOST=/cloudsql/$PROJECT_ID:$REGION:your-instance-name,DB_NAME=your-db,DB_USER=your-user,DB_PASSWORD=your-password,ALLOWED_ORIGINS=*"
```

### 4. Get Service URL

```bash
gcloud run services describe mcp-sse-server --region $REGION --format 'value(status.url)'
```

## Testing the Deployment

### 1. Health Check
```bash
curl https://your-service-url.run.app/health
```

Expected response:
```json
{"status": "healthy", "service": "mcp-sse-server"}
```

### 2. Test SSE Connection
```bash
curl -N https://your-service-url.run.app/sse
```

### 3. Test from Browser Console
```javascript
const eventSource = new EventSource('https://your-service-url.run.app/sse');

eventSource.onmessage = (event) => {
    console.log('Received:', event.data);
};

eventSource.onerror = (error) => {
    console.error('SSE Error:', error);
};
```

## Cloud Run Configuration Notes

### Port Configuration
- Cloud Run automatically sets the `PORT` environment variable
- The Dockerfile uses `${PORT}` to be compatible with Cloud Run's dynamic port assignment
- Default is 8080

### Timeout
- SSE connections need longer timeouts
- Cloud Run max timeout is 3600 seconds (1 hour)
- Adjust `--timeout` flag as needed

### Memory and CPU
- Start with 512Mi memory and 1 CPU
- Monitor usage and scale up if needed
- For database operations, 1Gi+ recommended

### Concurrency
- Default concurrency is 80
- For SSE, you may want to adjust:
```bash
gcloud run services update mcp-sse-server --concurrency 10
```

## Monitoring

### View Logs
```bash
gcloud run logs read mcp-sse-server --region $REGION --limit 50
```

### Real-time Logs
```bash
gcloud run logs tail mcp-sse-server --region $REGION
```

## Troubleshooting

### CORS Issues
- Check `Access-Control-Allow-Origin` headers in response
- Verify CORS middleware configuration
- Update `ALLOWED_ORIGINS` environment variable

### Connection Timeout
- Increase `--timeout` in deployment
- Check client-side timeout settings
- Verify SSE keepalive messages

### Database Connection Issues
- Verify Cloud SQL instance is running
- Check `--add-cloudsql-instances` flag
- Verify database credentials in environment variables
- Ensure Cloud Run service account has Cloud SQL Client role

## Security Best Practices

1. **Restrict Origins**: Update `allow_origins` to specific domains
2. **Authentication**: Add authentication middleware for production
3. **Rate Limiting**: Implement rate limiting for API endpoints
4. **Environment Variables**: Use Secret Manager for sensitive data
5. **Service Account**: Use minimal permissions for Cloud Run service account

## Cost Optimization

1. **Set min-instances to 0** for auto-scaling to zero when idle
2. **Use appropriate memory/CPU** based on actual usage
3. **Monitor request/response sizes** - Cloud Run charges for network egress
4. **Set max-instances** to prevent unexpected scaling costs

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Cloud SDK
        uses: google-github-actions/setup-gcloud@v0
        with:
          project_id: ${{ secrets.GCP_PROJECT_ID }}
          service_account_key: ${{ secrets.GCP_SA_KEY }}
      
      - name: Build and Push
        run: |
          gcloud builds submit --tag gcr.io/${{ secrets.GCP_PROJECT_ID }}/mcp-sse-server
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy mcp-sse-server \
            --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/mcp-sse-server \
            --region us-central1 \
            --platform managed \
            --allow-unauthenticated
```
