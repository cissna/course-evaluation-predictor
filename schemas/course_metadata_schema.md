# Course Metadata Schema

## Overview
Contains metadata about courses including tracking information for scraping and processing.

## Fields

| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| course_code | String | Unique identifier for the course in format DEPT.XXX.XXX | AS.001.100 |
| last_period_gathered | String | The most recent semester data was successfully gathered | SU25 |
| last_period_failed | Boolean | Whether the last gathering attempt failed | false |
| relevant_periods | Array | List of periods relevant to this course | [] |
| last_scrape_during_grace_period | String (nullable) | Indicates if last scrape occurred during grace period | (empty) |
| created_at | Timestamp | Record creation timestamp (UTC) | 2025-11-08 21:24:16.838723+00 |
| updated_at | Timestamp | Record last update timestamp (UTC) | 2025-11-08 21:24:19.346117+00 |

## Sample Records
- AS.000.000 (last updated 2025-11-08)
- AS.001.000 through AS.001.007 (last updated 2025-09-28)
