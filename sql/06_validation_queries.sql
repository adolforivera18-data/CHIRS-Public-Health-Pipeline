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
