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
