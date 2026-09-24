import time
import uuid
import boto3

REGION = "us-east-2"
ACCOUNT_ID = "152125350281"

BUCKET = "publichealth-project-data-lake-152125350281-us-east-2-an"
ATHENA_DATABASE = "public_health_db_curated"
ATHENA_WORKGROUP = "primary"
ATHENA_OUTPUT = f"s3://{BUCKET}/athena-results/"

QUICKSIGHT_DATASET_ID = "b1e5acf1-c401-4f1a-994b-02cc0a56feff"

CURATED_PREFIX = "curated/ny-state/chirs/current/"
DASHBOARD_PREFIX = "curated/ny-state/chirs/dashboard_current/"

athena = boto3.client("athena", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
quicksight = boto3.client("quicksight", region_name=REGION)


CHIRS_METRICS_SQL = f"""
CREATE TABLE public_health_db_curated.chirs_metrics
WITH (
  format = 'PARQUET',
  external_location = 's3://{BUCKET}/curated/ny-state/chirs/current/',
  parquet_compression = 'SNAPPY'
) AS
SELECT
  c.*,
  COALESCE(r.dsrip_region, c.geographic_area) AS dsrip_region,
  TRY_CAST(c.rate_percent AS DOUBLE) AS rate_percent_num,
  CAST(
    CASE
      WHEN c.data_year_title LIKE '%-%' THEN
        (
          TRY_CAST(SPLIT_PART(c.data_year_title, '-', 1) AS INTEGER)
          + TRY_CAST(SPLIT_PART(c.data_year_title, '-', 2) AS INTEGER)
        ) / 2
      ELSE TRY_CAST(c.data_year_title AS INTEGER)
    END AS INTEGER
  ) AS data_year_num,
  CASE
    WHEN c.data_year_title LIKE '%-%' THEN
      TRY_CAST(SPLIT_PART(c.data_year_title, '-', 2) AS INTEGER)
      - TRY_CAST(SPLIT_PART(c.data_year_title, '-', 1) AS INTEGER)
      + 1
    ELSE 1
  END AS data_year_span,
  CASE
    WHEN c.data_year_title LIKE '%-%'
      AND (
        TRY_CAST(SPLIT_PART(c.data_year_title, '-', 2) AS INTEGER)
        - TRY_CAST(SPLIT_PART(c.data_year_title, '-', 1) AS INTEGER)
        + 1
      ) = 3
      THEN 'three_year_average'
    WHEN c.data_year_title LIKE '%-%'
      AND (
        TRY_CAST(SPLIT_PART(c.data_year_title, '-', 2) AS INTEGER)
        - TRY_CAST(SPLIT_PART(c.data_year_title, '-', 1) AS INTEGER)
        + 1
      ) = 5
      THEN 'five_year_average'
    WHEN c.data_year_title LIKE '%-%'
      THEN 'multi_year_average'
    ELSE 'single_year'
  END AS data_year_period_type
FROM public_health_db_raw.raw_chirs_opencsv c
LEFT JOIN public_health_db_reference.ny_county_dsrip_region_mapping r
  ON c.geographic_area = r.geographic_area
WHERE
  CAST(c.extract_year AS INTEGER) * 100 + CAST(c.extract_month AS INTEGER) = (
    SELECT
      MAX(CAST(extract_year AS INTEGER) * 100 + CAST(extract_month AS INTEGER))
    FROM public_health_db_raw.raw_chirs_opencsv
  )
"""


CHIRS_DASHBOARD_SQL = f"""
CREATE TABLE public_health_db_curated.chirs_metrics_dashboard
WITH (
  format = 'PARQUET',
  external_location = 's3://{BUCKET}/curated/ny-state/chirs/dashboard_current/',
  parquet_compression = 'SNAPPY'
) AS
WITH source_geography AS (
  SELECT
    topic_area,
    indicator_title,
    geographic_area,
    dsrip_region,
    year_type,
    data_year_title,
    measurement,
    rate_percent,
    rate_percent_num,
    data_year_num,
    data_year_span,
    data_year_period_type,
    data_source,
    data_notes,
    extract_year,
    extract_month,
    'source_geography' AS geography_row_type
  FROM public_health_db_curated.chirs_metrics
),
dsrip_region_average AS (
  SELECT
    topic_area,
    indicator_title,
    dsrip_region AS geographic_area,
    dsrip_region,
    year_type,
    data_year_title,
    measurement,
    CAST(NULL AS VARCHAR) AS rate_percent,
    AVG(rate_percent_num) AS rate_percent_num,
    data_year_num,
    data_year_span,
    data_year_period_type,
    'Calculated from county values' AS data_source,
    'Simple average of county rates/percentages within DSRIP region' AS data_notes,
    extract_year,
    extract_month,
    'dsrip_region_average' AS geography_row_type
  FROM public_health_db_curated.chirs_metrics
  WHERE dsrip_region IS NOT NULL
    AND geographic_area <> 'New York State'
  GROUP BY
    topic_area,
    indicator_title,
    dsrip_region,
    year_type,
    data_year_title,
    measurement,
    data_year_num,
    data_year_span,
    data_year_period_type,
    extract_year,
    extract_month
),
state_excluding_nyc_average AS (
  SELECT
    topic_area,
    indicator_title,
    'New York State (excluding NYC)' AS geographic_area,
    'New York State (excluding NYC)' AS dsrip_region,
    year_type,
    data_year_title,
    measurement,
    CAST(NULL AS VARCHAR) AS rate_percent,
    AVG(rate_percent_num) AS rate_percent_num,
    data_year_num,
    data_year_span,
    data_year_period_type,
    'Calculated from DSRIP region averages excluding New York City' AS data_source,
    'Simple average of DSRIP region averages, excluding New York City' AS data_notes,
    extract_year,
    extract_month,
    'state_excluding_nyc_average' AS geography_row_type
  FROM dsrip_region_average
  WHERE geographic_area <> 'New York City'
  GROUP BY
    topic_area,
    indicator_title,
    year_type,
    data_year_title,
    measurement,
    data_year_num,
    data_year_span,
    data_year_period_type,
    extract_year,
    extract_month
)
SELECT * FROM source_geography
UNION ALL
SELECT * FROM dsrip_region_average
UNION ALL
SELECT * FROM state_excluding_nyc_average
"""


def delete_prefix(bucket, prefix):
    paginator = s3.get_paginator("list_objects_v2")
    to_delete = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            to_delete.append({"Key": obj["Key"]})

            if len(to_delete) == 1000:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": to_delete})
                to_delete = []

    if to_delete:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": to_delete})


def run_athena_query(query):
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
        WorkGroup=ATHENA_WORKGROUP,
    )

    query_execution_id = response["QueryExecutionId"]

    while True:
        result = athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = result["QueryExecution"]["Status"]["State"]

        if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
            break

        time.sleep(3)

    if state != "SUCCEEDED":
        reason = result["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
        raise RuntimeError(f"Athena query failed: {state}. Reason: {reason}")

    return query_execution_id


def refresh_quicksight_dataset():
    ingestion_id = f"refresh-{uuid.uuid4()}"

    return quicksight.create_ingestion(
        AwsAccountId=ACCOUNT_ID,
        DataSetId=QUICKSIGHT_DATASET_ID,
        IngestionId=ingestion_id,
    )


def lambda_handler(event, context):
    print("Starting public health pipeline refresh")

    print("Repairing raw CHIRS table partitions")
    run_athena_query("MSCK REPAIR TABLE public_health_db_raw.raw_chirs_opencsv")
    print("Raw CHIRS partitions repaired")

    print("Dropping chirs_metrics table")
    run_athena_query("DROP TABLE IF EXISTS public_health_db_curated.chirs_metrics")

    print(f"Deleting S3 prefix: s3://{BUCKET}/{CURATED_PREFIX}")
    delete_prefix(BUCKET, CURATED_PREFIX)

    print("Creating chirs_metrics table")
    run_athena_query(CHIRS_METRICS_SQL)
    print("chirs_metrics table created")

    print("Dropping chirs_metrics_dashboard table")
    run_athena_query("DROP TABLE IF EXISTS public_health_db_curated.chirs_metrics_dashboard")

    print(f"Deleting S3 prefix: s3://{BUCKET}/{DASHBOARD_PREFIX}")
    delete_prefix(BUCKET, DASHBOARD_PREFIX)

    print("Creating chirs_metrics_dashboard table")
    run_athena_query(CHIRS_DASHBOARD_SQL)
    print("chirs_metrics_dashboard table created")

    print("Starting QuickSight dataset refresh")
    ingestion_response = refresh_quicksight_dataset()
    print("QuickSight dataset refresh started")

    print("Public health pipeline refresh complete")

    return {
        "status": "success",
        "message": "Public health pipeline refreshed successfully.",
        "quicksight_ingestion": ingestion_response.get("Ingestion", {}),
    }
