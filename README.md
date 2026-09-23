# Public Health Data Pipeline

## Project Overview

This project is an AWS-based public health data pipeline that ingests New York State CHIRS public health CSV files, transforms them into curated Parquet datasets, creates custom regional comparison rows, and displays the final metrics in an Amazon QuickSight dashboard.

The pipeline was designed around a data lake pattern:

```text
Raw CSV files in Amazon S3
→ Athena external raw table
→ curated Parquet table
→ dashboard-ready Parquet table
→ QuickSight dashboard
```

The dashboard supports public health trend analysis by topic area, indicator, geography, and reporting period type. Users can compare counties, New York State, DSRIP regions, and New York State excluding New York City.

## Business Goal

The goal is to make public health indicator data easier to analyze and visualize by:

- Preserving raw source files in S3
- Creating reliable Athena tables over raw CSV files
- Transforming raw values into dashboard-ready numeric fields
- Adding custom DSRIP regional groupings
- Creating aggregated regional comparison rows
- Refreshing a QuickSight dashboard from a repeatable Lambda-driven pipeline

## AWS Services Used

| Service | Purpose |
|---|---|
| Amazon S3 | Stores raw CSV files, curated Parquet output, dashboard Parquet output, reference files, and Athena query results |
| AWS Glue Data Catalog | Stores databases, table schemas, partitions, and metadata used by Athena and QuickSight |
| Amazon Athena | Queries raw data and runs SQL transformations into Parquet tables |
| AWS Lambda | Orchestrates the refresh process by running Athena SQL, clearing S3 output folders, and refreshing QuickSight |
| Amazon QuickSight | Provides the interactive dashboard |
| IAM | Controls service permissions for Glue, Athena, S3, Lambda, and QuickSight |
| CloudWatch Logs | Captures Lambda execution logs and errors |

## S3 Data Lake Layout

Bucket:

```text
s3://publichealth-project-data-lake-152125350281-us-east-2-an/
```

Key prefixes:

```text
raw/ny-state/chirs/
reference/ny-state/dsrip-region-mapping/
curated/ny-state/chirs/current/
curated/ny-state/chirs/dashboard_current/
athena-results/
```

### Raw Layer

The raw CHIRS files are stored by extract period:

```text
raw/ny-state/chirs/extract_year=YYYY/extract_month=MM/version=raw/
```

Example:

```text
raw/ny-state/chirs/extract_year=2026/extract_month=09/version=raw/
```

Two files are uploaded for each extract:

- State-level CHIRS CSV
- County-level CHIRS CSV

Both files share the same structure, so Athena reads them as one combined raw table.

### Reference Layer

The DSRIP region mapping file is stored at:

```text
reference/ny-state/dsrip-region-mapping/ny_county_dsrip_region_mapping.csv
```

This file maps New York counties to DSRIP regions.

### Curated Layer

The base curated table writes Parquet output to:

```text
curated/ny-state/chirs/current/
```

The dashboard-ready table writes Parquet output to:

```text
curated/ny-state/chirs/dashboard_current/
```

QuickSight reads from the dashboard-ready table.

### Athena Results

Athena query result files are stored at:

```text
athena-results/
```

This is Athena's query output location. It is separate from the curated data used by the dashboard.

## Glue/Athena Databases

| Database | Purpose |
|---|---|
| `public_health_db_raw` | Raw external CSV tables |
| `public_health_db_reference` | Reference/mapping tables |
| `public_health_db_curated` | Curated and dashboard-ready Parquet tables |

## Raw CHIRS Table

Table:

```text
public_health_db_raw.raw_chirs_opencsv
```

Purpose:

- Reads raw CHIRS CSV files directly from S3
- Uses `OpenCSVSerde` to correctly handle values containing commas
- Uses S3 partition columns to identify extract year, extract month, and version

Raw columns:

```text
topic_area
indicator_title
geographic_area
year_type
data_year_title
measurement
rate_percent
data_source
data_notes
extract_year
extract_month
version
```

The table is partitioned by:

```text
extract_year
extract_month
version
```

After new raw files are uploaded, the pipeline runs:

```sql
MSCK REPAIR TABLE public_health_db_raw.raw_chirs_opencsv;
```

This discovers new S3 partitions so Athena can query the new extract.

## DSRIP Reference Table

Table:

```text
public_health_db_reference.ny_county_dsrip_region_mapping
```

Columns:

```text
geographic_area
dsrip_region
```

Purpose:

- Maps county rows to DSRIP regions
- Enables regional filtering and aggregation in the dashboard

DSRIP regions used:

```text
Western NY
Finger Lakes
Southern Tier
Central NY
Tug Hill Seaway
North Country
Mohawk Valley
Capital Region
Mid-Hudson
Long Island
New York City
```

## Curated Table

Table:

```text
public_health_db_curated.chirs_metrics
```

Purpose:

- Reads from the raw CHIRS table
- Filters to the latest extract only
- Joins county rows to the DSRIP mapping table
- Converts rate values to numeric format
- Creates year helper fields for trend analysis
- Writes the result as Parquet

Important transformed fields:

| Field | Purpose |
|---|---|
| `dsrip_region` | Region label joined from the county mapping table |
| `rate_percent_num` | Numeric version of `rate_percent` for charts and aggregations |
| `data_year_num` | Numeric year used for line chart X-axis sorting |
| `data_year_span` | Number of years represented by the data period |
| `data_year_period_type` | Labels periods as `single_year`, `three_year_average`, `five_year_average`, or `multi_year_average` |

Latest extract filter:

```sql
CAST(c.extract_year AS INTEGER) * 100 + CAST(c.extract_month AS INTEGER) = (
  SELECT
    MAX(CAST(extract_year AS INTEGER) * 100 + CAST(extract_month AS INTEGER))
  FROM public_health_db_raw.raw_chirs_opencsv
)
```

This prevents older extracts from mixing with newer extracts.

## Dashboard Table

Table:

```text
public_health_db_curated.chirs_metrics_dashboard
```

Purpose:

- Builds the final dataset used by QuickSight
- Includes original county and state rows
- Adds DSRIP regional average rows
- Adds a New York State excluding NYC comparison row

The table includes three row types:

| Row Type | Description |
|---|---|
| `source_geography` | Original county/state rows from the curated CHIRS data |
| `dsrip_region_average` | Simple average of county values within each DSRIP region |
| `state_excluding_nyc_average` | Simple average of DSRIP region averages excluding New York City |

This allows the same QuickSight `geographic_area` filter to include:

```text
Orange County
New York State
Mid-Hudson
Western NY
New York State (excluding NYC)
```

## Regional Aggregation Logic

DSRIP region rows are calculated as simple averages of county-level values:

```text
DSRIP region average = average of county rate_percent_num values within that region
```

New York State excluding NYC is calculated as:

```text
average of DSRIP region average rows, excluding New York City
```

This means each non-NYC DSRIP region contributes equally to the New York State excluding NYC comparison.

Important note:

These are simple averages, not population-weighted rates. A future enhancement could add population denominators and calculate weighted regional rates.

## QuickSight Dashboard

Dataset:

```text
chirs_metrics_dashboard
```

Source table:

```text
public_health_db_curated.chirs_metrics_dashboard
```

Main dashboard controls:

| Control | Field |
|---|---|
| Topic Area | `topic_area` |
| Indicator | `SelectedIndicator` parameter linked to `indicator_title` |
| Geography | `geographic_area` |
| Period Type | `data_year_period_type` |

The `SelectedIndicator` parameter drives:

- Indicator filtering
- Dynamic chart title
- Dynamic table title

Calculated field:

```text
series_name = concat({geographic_area}, ' - ', {data_year_period_type})
```

This creates chart and pivot labels such as:

```text
Orange County - single_year
Mid-Hudson - three_year_average
New York State - single_year
```

### Dashboard Visuals

The dashboard includes:

- Line chart showing indicator trends over time
- Pivot table with years as rows and selected geography/period series as columns
- Detail table showing source values, notes, and supporting metadata

Line chart fields:

```text
X-axis: data_year_num
Value: Average rate_percent_num
Color: series_name
```

Pivot table fields:

```text
Rows: data_year_num
Columns: series_name
Values: Average rate_percent_num
```

## Lambda Automation

Lambda function:

```text
public-health-refresh-pipeline
```

Execution role:

```text
PublicHealthPipelineAutomationRole
```

Purpose:

The Lambda function automates the manual Athena refresh process.

It performs these steps:

```text
1. Run MSCK REPAIR on the raw CHIRS table
2. Drop chirs_metrics
3. Delete old Parquet files from curated/ny-state/chirs/current/
4. Recreate chirs_metrics using Athena CTAS
5. Drop chirs_metrics_dashboard
6. Delete old Parquet files from curated/ny-state/chirs/dashboard_current/
7. Recreate chirs_metrics_dashboard using Athena CTAS
8. Trigger QuickSight dataset refresh
```

The Lambda uses:

```text
Athena start_query_execution
S3 delete_objects
QuickSight create_ingestion
```

## Manual Refresh Process

The current trigger strategy is manual. This is intentional because each extract requires two files:

- State-level CSV
- County-level CSV

If an automatic S3 upload trigger were used now, the pipeline could run after the first file uploads and before the second file is available. Manual execution avoids partial refreshes.

### Manual Run Checklist

1. Upload the state-level CSV to:

```text
raw/ny-state/chirs/extract_year=YYYY/extract_month=MM/version=raw/
```

2. Upload the county-level CSV to the same extract partition.

3. Confirm both files are present in S3.

4. Open Lambda:

```text
public-health-refresh-pipeline
```

5. Select the saved test event:

```text
RunPublicHealthPipeline
```

6. Click:

```text
Test
```

7. Confirm the Lambda result says:

```text
Status: Succeeded
```

8. Check QuickSight dataset refresh:

```text
Data → chirs_metrics_dashboard → Ingestions / Refresh history
```

9. Open the QuickSight dashboard and confirm the visuals updated.

## Future Automation Option: `_READY` File Trigger

A future improvement is to use an S3 trigger based on a marker file.

Future S3 layout:

```text
raw/ny-state/chirs/extract_year=2027/extract_month=09/version=raw/
  state.csv
  county.csv
  _READY
```

The pipeline would trigger only when `_READY` is uploaded.

This would prevent the Lambda from running too early after only one data file is uploaded.

## Validation Queries

Check dashboard row types:

```sql
SELECT
  geography_row_type,
  COUNT(*) AS row_count
FROM public_health_db_curated.chirs_metrics_dashboard
GROUP BY geography_row_type
ORDER BY geography_row_type;
```

Check latest extract:

```sql
SELECT
  extract_year,
  extract_month,
  COUNT(*) AS row_count
FROM public_health_db_curated.chirs_metrics
GROUP BY extract_year, extract_month
ORDER BY extract_year, extract_month;
```

Check selectable regional geographies:

```sql
SELECT DISTINCT
  geographic_area,
  geography_row_type
FROM public_health_db_curated.chirs_metrics_dashboard
ORDER BY geography_row_type, geographic_area;
```

Check New York State excluding NYC:

```sql
SELECT DISTINCT
  geographic_area,
  geography_row_type
FROM public_health_db_curated.chirs_metrics_dashboard
WHERE geographic_area = 'New York State (excluding NYC)';
```

## Design Decisions

### Why Use S3 and Athena Instead of a Traditional Database?

The project uses a serverless data lake architecture. S3 stores the data, Glue stores the metadata, and Athena provides SQL querying. This avoids managing a database server while still supporting analytics and dashboarding.

### Why Use Parquet for Curated Data?

Parquet is columnar, compressed, and efficient for Athena and QuickSight queries. It is better suited for analytics than repeatedly querying raw CSV files.

### Why Use Lambda?

Lambda automates the refresh process without requiring a server. It replaces manual Athena query execution and QuickSight refresh steps.

### Why Keep Manual Triggering for Now?

Manual triggering prevents partial refreshes because each extract currently depends on both a state-level file and a county-level file.

### Why Add Region Rows in Athena Instead of QuickSight?

Regional rows are created in Athena so that QuickSight can treat DSRIP regions like normal geographies. This keeps dashboard logic simpler and reusable.

## Current Limitations

- Regional averages are simple averages, not population-weighted rates.
- The pipeline currently uses a manual Lambda test event as the run trigger.
- The Y-axis label in QuickSight is kept generic because QuickSight does not natively auto-update the axis title from the selected indicator's `measurement` field without additional parameter/control logic.
- The dashboard depends on the curated table schema remaining stable.

## Future Enhancements

- Add population denominator data for weighted regional rates
- Add `_READY` file S3 trigger
- Move orchestration to Step Functions for better step-level visibility
- Add automated data quality checks before QuickSight refresh
- Add failure notifications through Amazon SNS or email
- Store SQL scripts in source control or S3 for easier maintenance
- Add a formal data dictionary

## Project Summary

This project demonstrates a complete AWS analytics workflow:

```text
S3 raw storage
→ Athena/Glue external raw table
→ reference mapping table
→ Athena SQL transformations
→ curated Parquet output
→ dashboard-ready regional aggregations
→ Lambda automation
→ QuickSight dashboard
```

It shows practical experience with cloud data engineering, serverless analytics, SQL transformation logic, partitioned data lake design, dashboard modeling, and AWS automation.
