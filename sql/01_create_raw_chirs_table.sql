CREATE EXTERNAL TABLE public_health_db_raw.raw_chirs_opencsv (
  geographic_area string,
  topic_area string,
  indicator_title string,
  year_type string,
  data_year_title string,
  numerator string,
  measurement string,
  rate_percent string,
  data_source string,
  data_notes string
)
PARTITIONED BY (
  extract_year string,
  extract_month string,
  version string
)
ROW FORMAT SERDE 'org.apache.hadoop.hive.serde2.OpenCSVSerde'
WITH SERDEPROPERTIES (
  'separatorChar' = ',',
  'quoteChar' = '"',
  'escapeChar' = '\\'
)
STORED AS TEXTFILE
LOCATION 's3://publichealth-project-data-lake-152125350281-us-east-2-an/raw/ny-state/chirs/'
TBLPROPERTIES (
  'skip.header.line.count'='1'
);
