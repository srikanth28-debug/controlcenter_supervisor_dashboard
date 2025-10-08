# TECO Lambda Admin Dashboard (Refactored)

**Handler:** `handler.lambda_handler`

## Environment Variables
- AWS_REGION (default: us-east-1)
- CONNECT_INSTANCE_ID (required)
- DDB_TABLE_MAPPING (used by post_agent_proficiency_assignment)
- DDB_TABLE_PROFILES (used by post_agent_proficiency_assignment)
- LOG_LEVEL (default: INFO)
- Additional env keys auto-generated for tables detected in route files: DDB_TABLE_<TABLE_NAME>

## Structure
- routes/ — endpoint modules (refactored to share utils)
- utils/ — shared helpers (logger, http, aws clients)
- handler.py — router mapping API Gateway resource paths to route handlers
