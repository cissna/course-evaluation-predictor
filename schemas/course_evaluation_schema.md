# Course Evaluation Data Schema

## Overview
Contains detailed course evaluation feedback organized by instance and semester, with aggregated survey response frequencies.

## Fields

| Field Name | Data Type | Description | Example |
|------------|-----------|-------------|---------|
| instance_key | String | Unique identifier combining course code and semester in format CODE.SECTION.SEMESTER | AS.001.100.01.FA21 |
| course_code | String | Reference to the course code | AS.001.100 |
| data | JSON String | Serialized evaluation data containing survey responses and metadata | (see Data Structure below) |
| created_at | Timestamp | Record creation timestamp (UTC) | 2025-09-23 21:57:09.46272+00 |
| updated_at | Timestamp | Record last update timestamp (UTC) | 2025-09-23 21:57:09.46272+00 |

## Data Structure (JSON within `data` field)

### Top-level Properties
- **ta_names** (Array): List of teaching assistant names
- **course_name** (String): Full course title
- **instructor_name** (String): Instructor's name
- **ta_frequency** (Object): Count distribution of TA ratings
- **feedback_frequency** (Object): Count distribution of feedback survey responses
- **workload_frequency** (Object): Count distribution of workload assessments
- **overall_quality_frequency** (Object): Count distribution of overall course quality ratings
- **intellectual_challenge_frequency** (Object): Count distribution of intellectual challenge ratings
- **instructor_effectiveness_frequency** (Object): Count distribution of instructor effectiveness ratings

### Frequency Objects
Each frequency object contains response categories with integer counts:
- **ta_frequency**: N/A, Good, Poor, Weak, Excellent, Satisfactory
- **feedback_frequency**: N/A, Agree somewhat, Agree strongly, Disagree somewhat, Disagree strongly, Neither agree nor disagree
- **workload_frequency**: N/A, Typical, Much heavier, Much lighter, Somewhat heavier, Somewhat lighter
- **overall_quality_frequency**: N/A, Good, Poor, Weak, Excellent, Satisfactory
- **intellectual_challenge_frequency**: N/A, Good, Poor, Weak, Excellent, Satisfactory
- **instructor_effectiveness_frequency**: N/A, Good, Poor, Weak, Excellent, Satisfactory

## Sample Records
- AS.001.100.01.FA21: "FYS: What is the Common Good?" taught by Aliza Watters (Fall 2021)
- AS.001.101.01.FA24: "FYS: The Hospital" taught by Bill Leslie (Fall 2024)
- AS.001.102.01.FA21: "FYS: Japanese Robots" taught by Yulia Frumer (Fall 2021)
