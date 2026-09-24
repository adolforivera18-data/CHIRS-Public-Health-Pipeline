# Lambda Configuration

Function name:

```text
public-health-refresh-pipeline
```

Execution role:

```text
PublicHealthPipelineAutomationRole
```

Purpose:

This Lambda function orchestrates the public health data pipeline refresh.

Refresh steps:

1. Repair raw CHIRS Athena partitions.
2. Drop the curated CHIRS metrics table.
3. Delete old curated Parquet files from S3.
4. Recreate the curated CHIRS metrics table with Athena CTAS.
5. Drop the dashboard CHIRS metrics table.
6. Delete old dashboard Parquet files from S3.
7. Recreate the dashboard CHIRS metrics table with Athena CTAS.
8. Trigger the QuickSight dataset refresh.

Trigger strategy:

The function is currently run manually from a saved Lambda test event after both the state-level and county-level CHIRS CSV files have been uploaded.
