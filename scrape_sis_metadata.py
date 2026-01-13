import requests
import csv
import time
import os
import logging
import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

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
                    if not row:
                        continue
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

def count_set_bits(n: int) -> int:
    """Counts the number of set bits (1s) in an integer."""
    count = 0
    while n > 0:
        n &= (n - 1)
        count += 1
    return count

def fetch_course_history(course_code: str, api_key: str) -> List[Dict[str, Any]]:
    """Queries SIS API for all historical sections of a course."""
    clean_code = course_code.replace(".", "")
    url = f"{API_BASE_URL}/{clean_code}"
    params = {"key": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=30)
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

def fetch_bulk_section_history(course_code: str, target_section: str, api_key: str) -> Optional[List[Dict[str, Any]]]:
    """
    Attempts to fetch the full history of a section (e.g. AS17110101).
    Returns None if the request fails (timeout/500), indicating a need for fallback.
    """
    clean_code = course_code.replace(".", "")
    url = f"{API_BASE_URL}/{clean_code}{target_section}"
    params = {"key": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # If API returns an error message dict, treat as failure
        if isinstance(data, dict) and "Message" in data:
             return None
        
        return data
    except Exception:
        # On ANY error (timeout, 500, json decode), return None to trigger fallback
        return None

def fetch_section_details_single_term(course_code: str, target_section: str, term: str, api_key: str) -> List[Dict[str, Any]]:
    """
    Queries SIS API for a specific section in a specific term to get SectionDetails.
    """
    clean_code = course_code.replace(".", "")
    import urllib.parse
    encoded_term = urllib.parse.quote(term)
    
    url = f"{API_BASE_URL}/{clean_code}{target_section}/{encoded_term}"
    params = {"key": api_key}
    
    try:
        response = requests.get(url, params=params, timeout=10) # Shorter timeout for individual terms
        response.raise_for_status()
        data = response.json()
        
        if isinstance(data, dict) and "Message" in data:
             return []
        
        return data
    except Exception as e:
        logging.error(f"Error fetching details for {course_code} {term}: {e}")
        return []

def extract_features(course_code: str, 

                     course_history: List[Dict[str, Any]], 

                     details_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

    """

    Processes raw API data to extract features per semester.

    Merges general course history with specific section details.

    """

    if not course_history:

        return []



    # 1. Build Lookup Map (Term -> {desc, prereqs})

    # This handles both Bulk (list of all terms) and Iterative (list of all terms) inputs.

    details_map = {}

    for section in details_list:

        term = section.get("Term")

        if not term: continue

        

        # Extract details

        sec_details = section.get("SectionDetails", [])

        desc = ""

        prereq_str = ""

        

        if isinstance(sec_details, list) and len(sec_details) > 0:

            detail_obj = sec_details[0]

            desc = detail_obj.get("Description", "")

            

            p_list = detail_obj.get("Prerequisites", [])

            p_parts = []

            if isinstance(p_list, list):

                for p_item in p_list:

                    if isinstance(p_item, dict):

                        p_desc = p_item.get("Description", "")

                        if p_desc:

                            p_parts.append(p_desc)

            prereq_str = "; ".join(p_parts)



        details_map[term] = {

            "description": desc,

            "prerequisites": prereq_str

        }



    # 2. Group Main History by Semester

    semesters = defaultdict(list)

    for section in course_history:

        term = section.get("Term")

        if term:

            semesters[term].append(section)

    

    results = []



    for term, sections in semesters.items():

        try:

            total_enrollment = 0

            total_capacity = 0

            max_credits = 0.0

            all_instructors = set()

            start_times = []

            meets_friday = False

            num_days = 0

            

            titles = set()

            buildings = set()

            locations = set()

            areas = set()

            instruction_methods = set()

            is_writing_intensive = False 



            for section in sections:

                # Capacity & Enrollment

                try:

                    cap = int(section.get("MaxSeats", 0))

                    open_s = int(section.get("OpenSeats", 0))

                    total_capacity += cap

                    total_enrollment += (cap - open_s)

                except (ValueError, TypeError):

                    pass



                # Credits

                try:

                    c = float(section.get("Credits", 0))

                    if c > max_credits:

                        max_credits = c

                except (ValueError, TypeError):

                    pass



                # Instructors

                instr = section.get("InstructorsFullName", "")

                if instr:

                    all_instructors.add(instr)

                

                # Days checks

                try:

                    dow = int(section.get("DOW", 0))

                    # Friday check (bit 16)

                    if dow & 16:

                        meets_friday = True

                    

                    # Count days (bits set)

                    # We take the max of sections? Or just the first valid one?

                    # Usually sections have same pattern. Let's take the max found.

                    d = count_set_bits(dow)

                    if d > num_days:

                        num_days = d

                except (ValueError, TypeError):

                    pass

                

                # Earliest Start Time

                dow_sort = section.get("DOWSort", "")

                if "^" in dow_sort:

                    time_str = dow_sort.split("^")[1]

                    t_float = parse_time_to_float(time_str)

                    if t_float is not None:

                        start_times.append(t_float)



                # New Fields

                t = section.get("Title", "").strip()

                if t: titles.add(t)



                wi = section.get("IsWritingIntensive", "")

                if wi and wi.lower() == "yes":

                    is_writing_intensive = True

                

                b = section.get("Building", "").strip()

                if b: buildings.add(b)



                l = section.get("Location", "").strip()

                if l: locations.add(l)



                a = section.get("Areas", "").strip()

                if a and a.lower() != "none": areas.add(a)



                im = section.get("InstructionMethod", "").strip()

                if im: instruction_methods.add(im)



            earliest_start = min(start_times) if start_times else None

            

            # Lookup details for this term

            term_details = details_map.get(term, {})

            

            row = {

                "course_code": course_code,

                "semester": term,

                "start_time_24h": earliest_start,

                "is_friday": meets_friday,

                "num_days_with_class": num_days,

                "max_capacity": total_capacity,

                "actual_enrollment": total_enrollment,

                "credits": max_credits,

                "instructors": "; ".join(sorted(list(all_instructors))),

                "title": "; ".join(sorted(list(titles))),

                "is_writing_intensive": is_writing_intensive,

                "buildings": "; ".join(sorted(list(buildings))),

                "locations": "; ".join(sorted(list(locations))),

                "areas": "; ".join(sorted(list(areas))),

                "instruction_methods": "; ".join(sorted(list(instruction_methods))),

                "description": term_details.get("description", ""),

                "prerequisites": term_details.get("prerequisites", "")

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
        "course_code", "semester", "start_time_24h", "is_friday", "num_days_with_class",
        "max_capacity", "actual_enrollment", "credits", "instructors",
        "title", "is_writing_intensive", "buildings", "locations", 
        "areas", "instruction_methods", "description", "prerequisites"
    ]
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for code in tqdm(codes, desc="Fetching Metadata"):
            try:
                # 1. Fetch Full Course History
                course_history = fetch_course_history(code, api_key)
                if not course_history:
                    # If history is empty, no need to proceed
                    continue
                
                # 2. Determine Target Section for Details
                target_section = "01"
                found_01 = False
                for section in course_history:
                    if str(section.get("SectionName", "")).strip() == "01":
                        found_01 = True
                        break
                if not found_01 and len(course_history) > 0:
                    # Fallback to the most recent section's name
                    target_section = str(course_history[-1].get("SectionName", "01"))

                # 3. Try Bulk Fetch (Try 1)
                section_details_history = fetch_bulk_section_history(code, target_section, api_key)
                
                # 4. Fallback: Iterative Fetch per Term
                if section_details_history is None:
                    # print(f"  -> Bulk fetch failed for {code}, switching to iterative mode...")
                    section_details_history = []
                    # Get unique terms from history
                    unique_terms = set(s.get("Term") for s in course_history if s.get("Term"))
                    
                    for term in unique_terms:
                        # Fetch details for this specific term
                        # We use the target_section (e.g. 01)
                        term_details = fetch_section_details_single_term(code, target_section, term, api_key)
                        if term_details:
                            section_details_history.extend(term_details)
                        time.sleep(0.05) # Small sleep between term requests

                # 5. Extract & Merge
                rows = extract_features(code, course_history, section_details_history)
                
                # 6. Write
                for row in rows:
                    writer.writerow(row)
                
                # Rate limiting
                time.sleep(0.2) 
                
            except Exception as e:
                logging.error(f"Unexpected error processing {code}: {e}")
                print(f"Error processing {code}. See log.")
                
    print(f"\nDone. Results saved to {OUTPUT_FILE}")
    print("Errors (if any) logged to sis_errors.log")

if __name__ == "__main__":
    main()
