# Lambda Package (Commonized)

- Entry point: `handler.lambda_handler`
- All routes import shared helpers from `utils/`:
  - `utils.http.respond`, `utils.http.cors_headers`
  - `utils.logger.get_logger`
  - `utils.aws_clients.ddb`, `utils.aws_clients.connect`, `utils.aws_clients.table`

## Environment Variables
- `AWS_REGION` (default: `us-east-1`)
- `CONNECT_INSTANCE_ID` (required for Connect routes)
- `LOG_LEVEL` (default: `INFO`)
- DynamoDB tables (define per environment):
- **DDB_TABLE_TECO_DYNAMODB_BUSINESS_GROUP_CONFIGS_US_EAST_1_DEV** = `teco-dynamodb-business-group-configs-us-east-1-dev`
- **DDB_TABLE_TECO_DYNAMODB_CALLFLOW_PROMPTS_US_EAST_1_DEV** = `teco-dynamodb-callflow-prompts-us-east-1-dev`
- **DDB_TABLE_TECO_EMAIL_TEMPLATES** = `teco_email_templates`
- **DDB_TABLE_TECO_PROFICIENCY_PROFILE_AGENT_MAPPING_US_EAST_1_DEV** = `teco-proficiency-profile-agent-mapping-us-east-1-dev`
- **DDB_TABLE_TECO_PROFICIENCY_PROFILE_US_EAST_1_DEV** = `teco-proficiency-profile-us-east-1-dev`
- **DDB_TABLE_TECO_PROFILE_PERMISSIONS_REACT_TABLE** = `teco-profile-permissions-react-table`
- **DDB_TABLE_TECO_USER_PERMISSION_REACT_TABLE** = `teco-user-permission-react-table`
