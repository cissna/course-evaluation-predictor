import requests
import csv
import time
import os
import logging
import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Optional

# Setup logging
logging.basicConfig(
    filename='sis_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# TQDM for progress bar (optional)
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        print("tqdm not installed, showing simple progress...")
        return iterable

# Configuration
API_BASE_URL = "https://sis.jhu.edu/api/classes"
OUTPUT_FILE = os.path.join("data", "sis_metadata_enriched.csv")
INPUT_FILE = os.path.join("data", "unique_course_codes.csv")

def get_api_key() -> Optional[str]:
    """Retrieves the JHU SIS API key from environment variable."""
    api_key = os.environ.get("SIS_API_KEY")
    if not api_key:
        print("SIS_API_KEY environment variable not found.")
        # Optional: Ask user input if interactive, but for automation scripts env var is preferred. 
        # api_key = input("Please enter your JHU SIS API key: ").strip() 
    return api_key

def load_course_codes() -> List[str]:
    """
    Loads course codes from data/unique_course_codes.csv.
    If file doesn't exist, returns a dummy list for testing.
    """
    if os.path.exists(INPUT_FILE):
        print(f"Loading course codes from {INPUT_FILE}...")
        codes = []
        try:
            with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                # Assume header exists? Or just a list?
                # Prompt implies "containing a list of course codes". 
                # We'll check if the first row looks like a header.
                for row in reader:
                    if not row: continue
                    val = row[0].strip()
                    # Simple heuristic to skip header "course_code" if present
                    if val.lower() == "course_code":
                        continue
                    codes.append(val)
            print(f"Loaded {len(codes)} codes.")
            return codes
        except Exception as e:
            print(f"Error reading {INPUT_FILE}: {e}")
            return []
    else:
        print(f"Warning: {INPUT_FILE} not found. Using placeholder data.")
        return ["AS.171.101", "EN.601.226", "AS.110.202"]

def parse_time_to_float(time_str: str) -> Optional[float]:
    """
    Converts a time string (e.g., '13:30:00' or '1:30 PM') to a float 24h format (e.g., 13.5).
    """
    if not time_str:
        return None
    
    # Clean string
    time_str = time_str.strip()
    
    try:
        # Try HH:MM:SS format (common in APIs)
        dt = datetime.strptime(time_str, "%H:%M:%S")
        return dt.hour + dt.minute / 60.0
    except ValueError:
        pass

    try:
        # Try 12-hour format with AM/PM
        dt = datetime.strptime(time_str, "%I:%M %p")
        return dt.hour + dt.minute / 60.0
    except ValueError:
        pass
    
    return None

def parse_prerequisites(prereq_data: Any) -> str:
    """
    Parses the Prerequisites field which might be a string or a list of dicts.
    Returns a single string description.
    """
    if not prereq_data:
        return ""
    
    if isinstance(prereq_data, str):
        return prereq_data.strip()
        
    if isinstance(prereq_data, list):
        # API docs suggest it's a set of records with "Description"
        descriptions = []
        for item in prereq_data:
            if isinstance(item, dict):
                desc = item.get("Description", "")
                if desc:
                    descriptions.append(desc)
            elif isinstance(item, str):
                descriptions.append(item)
        return "; ".join(descriptions)
        
    return ""

def fetch_course_history(course_code: str, api_key: str) -> List[Dict[str, Any]]:
    """Queries SIS API for all historical sections of a course."""
    url = f"{API_BASE_URL}/{course_code}"
    params = {"key": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # SIS API sometimes returns {"Message": "No records found"}
        if isinstance(data, dict) and "Message" in data:
            return []
            
        return data # Should be a list of section objects
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error fetching {course_code}: {e}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error for {course_code}: {e}")
        return []

def extract_features(course_code: str, api_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Processes raw API data to extract features per semester."""
    if not api_data:
        return []

    # Group by Semester (Term)
    # Key: Term String (e.g. "Fall 2023")
    # Value: List of section objects
    semesters = defaultdict(list)
    for section in api_data:
        term = section.get("Term")
        if term:
            semesters[term].append(section)
    
    results = []

    for term, sections in semesters.items():
        try:
            # Initialize aggregators
            total_enrollment = 0
            total_capacity = 0
            max_credits = 0.0
            all_instructors = set()
            start_times = []
            meets_friday = False
            prereq_text = ""
            
            for section in sections:
                # Enrollment
                try:
                    total_enrollment += int(section.get("ActualEnrollment", 0))
                except (ValueError, TypeError):
                    pass
                
                # Capacity
                try:
                    total_capacity += int(section.get("MaxSeating", 0))
                except (ValueError, TypeError):
                    pass

                # Credits
                try:
                    c = float(section.get("Credits", 0))
                    if c > max_credits:
                        max_credits = c
                except (ValueError, TypeError):
                    pass

                # Prerequisites (Take the first non-empty one we find for this semester)
                if not prereq_text:
                    p = parse_prerequisites(section.get("Prerequisites"))
                    if p:
                        prereq_text = p

                # Instructors
                # "Instructors" is often a list of dicts in SIS API
                instrs = section.get("Instructors", [])
                if isinstance(instrs, list):
                    for i in instrs:
                        # Try to construct name
                        if isinstance(i, dict):
                            fname = i.get("FirstName", "")
                            lname = i.get("LastName", "")
                            name = f"{fname} {lname}".strip()
                            if name:
                                all_instructors.add(name)
                
                # Meeting Times
                # "MeetingPatterns" is usually a list of dicts
                meetings = section.get("MeetingPatterns", [])
                if isinstance(meetings, list):
                    for m in meetings:
                        if not isinstance(m, dict): continue
                        
                        days = m.get("Days", "")
                        start = m.get("StartTime", "")
                        
                        # Check Friday
                        if days and ("F" in days or "Fri" in days):
                            meets_friday = True
                        
                        # Collect start time
                        if start:
                            t_float = parse_time_to_float(start)
                            if t_float is not None:
                                start_times.append(t_float)

            # Feature logic
            earliest_start = min(start_times) if start_times else None
            
            row = {
                "course_code": course_code,
                "semester": term,
                "start_time_24h": earliest_start,
                "is_friday": meets_friday,
                "max_capacity": total_capacity,
                "actual_enrollment": total_enrollment,
                "credits": max_credits,
                "instructors": "; ".join(sorted(list(all_instructors))),
                "prerequisites": prereq_text
            }
            results.append(row)

        except Exception as e:
            logging.error(f"Error parsing data for {course_code} {term}: {e}")
            continue

    return results

def main():
    api_key = get_api_key()
    if not api_key:
        print("Aborting: No API Key.")
        return

    codes = load_course_codes()
    if not codes:
        print("No course codes to process.")
        return

    print(f"Processing {len(codes)} courses...")
    
    # Prepare CSV Output
    fieldnames = [
        "course_code", "semester", "start_time_24h", "is_friday",
        "max_capacity", "actual_enrollment", "credits", "instructors",
        "prerequisites"
    ]
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for code in tqdm(codes, desc="Fetching Metadata"):
            try:
                # 1. Fetch
                raw_data = fetch_course_history(code, api_key)
                if not raw_data:
                    continue
                
                # 2. Extract
                rows = extract_features(code, raw_data)
                
                # 3. Write
                for row in rows:
                    writer.writerow(row)
                
                # Rate limiting
                time.sleep(0.1) 
                
            except Exception as e:
                logging.error(f"Unexpected error processing {code}: {e}")
                print(f"Error processing {code}. See log.")
                
    print(f"\nDone. Results saved to {OUTPUT_FILE}")
    print("Errors (if any) logged to sis_errors.log")

if __name__ == "__main__":
    main()
