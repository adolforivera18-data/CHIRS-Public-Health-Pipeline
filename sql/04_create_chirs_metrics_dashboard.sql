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
