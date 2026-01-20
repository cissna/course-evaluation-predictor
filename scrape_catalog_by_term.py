import csv
import json
import os
import logging
import urllib.parse
from api_client import APIClient
from datetime import datetime
import shutil
from collections import defaultdict

# Configure Logging
logging.basicConfig(
    filename='catalog_scrape.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Constants
OUTPUT_FILE = os.path.join("data", "jhu_course_catalog_full.csv")
API_BASE_URL = "https://sis.jhu.edu/api/classes"

def generate_terms():
    """Generates a list of terms from Fall 2010 to present."""
    seasons = ['Intersession', "Spring", "Summer", "Fall"]
    terms = []
    start_year = 2010
    current_date = datetime.now()
    end_year = current_date.year
    
    for year in range(start_year, end_year + 1):
        for season in seasons:
            # Don't add future terms for the current year if they haven't happened/aren't listed? 
            # Actually, usually safer to just add them all for current year.
            terms.append(f"{season} {year}")
            
    # Add next year's Intersession/Spring if we are late in the year
    if current_date.month >= 8:
        terms.append(f"Intersession {end_year + 1}")
        terms.append(f"Spring {end_year + 1}")
        
    return terms

def process_section_row(section_data, details_map):
    """
    Transforms a raw section record into a CSV-ready row, 
    injecting Description/Prereqs from the details_map.
    """
    term = section_data.get("Term")
    course_name = section_data.get("OfferingName")
    
    # Base Data
    row = {
        "Term": term,
        "CourseCode": course_name,
        "SectionName": section_data.get("SectionName", ""),
        "Title": section_data.get("Title", ""),
        "Instructors": section_data.get("InstructorsFullName", ""),
        "Credits": section_data.get("Credits", ""),
        "Status": section_data.get("Status", ""),
        "Level": section_data.get("Level", ""),
        "Area": section_data.get("Areas", ""),
        "Building": section_data.get("Building", ""),
        "Location": section_data.get("Location", ""),
        "InstructionMethod": section_data.get("InstructionMethod", ""),
        "MaxSeats": section_data.get("MaxSeats", ""),
        "OpenSeats": section_data.get("OpenSeats", ""),
        "DOW": section_data.get("DOW", ""),       # Raw DOW
        "DOWSort": section_data.get("DOWSort", ""), # Raw DOWSort
        "Description": "",
        "Prereq_JSON": "[]",
        "CoReq_JSON": "[]"
    }

    # Inject Details if available for this Term
    if term in details_map:
        d = details_map[term]
        row["Description"] = d.get("Description", "")
        row["Prereq_JSON"] = d.get("Prerequisites", "[]")
        row["CoReq_JSON"] = d.get("CoRequisites", "[]")
        
    return row

def extract_details_from_history(history_data):
    """
    Parses a list of section history records (which contain SectionDetails)
    into a map: Term -> {Description, Prerequisites, CoRequisites}
    """
    mapping = {}
    if not history_data:
        return mapping

    for record in history_data:
        term = record.get("Term")
        if not term:
            continue
        
        details_list = record.get("SectionDetails", [])
        if isinstance(details_list, list) and len(details_list) > 0:
            detail = details_list[0]
            
            # Extract raw JSON blobs
            prereqs = detail.get("Prerequisites", [])
            coreqs = detail.get("CoRequisites", [])
            
            mapping[term] = {
                "Description": detail.get("Description", ""),
                "Prerequisites": json.dumps(prereqs) if prereqs else "[]",
                "CoRequisites": json.dumps(coreqs) if coreqs else "[]"
            }
    return mapping

def main():
    client = APIClient(requests_per_minute=100)
    if not client.api_key:
        print("Error: SIS_API_KEY not set.")
        return

    # 1. Setup Output File
    fieldnames = [
        "Term", "CourseCode", "SectionName", "Title", 
        "Instructors", "Credits", "Status", "Level", "Area",
        "Building", "Location", "InstructionMethod",
        "MaxSeats", "OpenSeats", "DOW", "DOWSort",
        "Description", "Prereq_JSON", "CoReq_JSON"
    ]
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    if os.path.exists(OUTPUT_FILE):
        name, extension = OUTPUT_FILE, ''
        if '.' in OUTPUT_FILE:
            name, extension = OUTPUT_FILE.rsplit('.', 1)
            extension = '.' + extension
            
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        shutil.move(OUTPUT_FILE, f"{name}.{timestamp}.bak{extension}")
    
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

    # 2. Term Sweep (Catalog Building)
    # We will accumulate ALL sections for ALL terms into memory first?
    # No, that's too big. We should process year-by-year or school-by-school.
    # But to do the "Set Cover" optimization effectively, we need the FULL picture of a Course's history.
    # Compromise: We will iterate Terms to find all Course Codes, but we will store 
    # the "Skeleton" of the catalog in memory (grouped by CourseCode).
    # Then we iterate Courses to fill in details.
    
    print("Phase 1: Term Sweep (Building Catalog Skeleton)...")
    
    terms = generate_terms()
    schools = ["Krieger School of Arts and Sciences", "Whiting School of Engineering"]
    
    # Master structure: CourseCode -> { Term -> [List of Section Objects] }
    # This stores the "lite" data from the Term Sweep.
    catalog_skeleton = defaultdict(lambda: defaultdict(list))
    
    for term in terms:
        logging.info(f"Scanning {term}...")
        print(f"Scanning {term}...")
        encoded_term = urllib.parse.quote(term)
        
        for school in schools:
            encoded_school = urllib.parse.quote(school)
            url = f"{API_BASE_URL}/{encoded_school}/{encoded_term}"
            
            # This returns ALL sections for the school/term
            data = client.make_request(url)
            
            if not data or not isinstance(data, list):
                continue
                
            for section in data:
                c_code = section.get("OfferingName")
                if not c_code:
                    continue
                
                # Store this section under the Course -> Term
                catalog_skeleton[c_code][term].append(section)

    print(f"Phase 1 Complete. Found {len(catalog_skeleton)} unique courses.")
    print("Phase 2: Set Cover Optimization & Detail Fetching...")
    
    # 3. Process Each Course
    with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        
        for i, (course_code, term_map) in enumerate(catalog_skeleton.items()):
            # TEST MODE: Only process one course
            # print("!!! TEST MODE: Processing only the first course found !!!")
            # if i > 0: break 
            
            print(f"Processing Test Course: {course_code}")
            
            # term_map is { "Fall 2023": [Sec01, Sec02], "Spring 2024": [Sec01] }
            
            # A. Build the Matrix for Set Cover
            # Map: Term -> Set(SectionNames)
            term_to_sections = {}
            all_terms_needed = set(term_map.keys())
            
            for term, section_list in term_map.items():
                s_names = set(s.get("SectionName", "") for s in section_list)
                term_to_sections[term] = s_names

            # B. The Greedy Algorithm
            # We need to find details for ALL terms in `all_terms_needed`.
            # We have a map `fetched_details` that will store Term -> {Desc, Prereq}
            fetched_details = {}
            
            uncovered_terms = all_terms_needed.copy()
            
            while uncovered_terms:
                # 1. Identify candidate sections
                # Find which section name appears in the most UNCOVERED terms
                candidate_counts = defaultdict(int)
                
                # Priority: Single-section terms (we MUST fetch these eventually)
                must_pick_candidates = set()
                
                for term in uncovered_terms:
                    available_sections = term_to_sections[term]
                    if len(available_sections) == 1:
                        must_pick_candidates.add(list(available_sections)[0])
                    
                    for s_name in available_sections:
                        candidate_counts[s_name] += 1
                
                # Pick the winner
                best_section = None
                
                if must_pick_candidates:
                    # If we have terms with ONLY one section, pick one of those sections.
                    # It covers at least 1 term, maybe more.
                    # Pick the one that covers the MOST uncovered terms among the forced choices.
                    best_section = max(must_pick_candidates, key=lambda s: candidate_counts[s])
                else:
                    # Otherwise, just pick the section appearing most often
                    best_section = max(candidate_counts, key=candidate_counts.get)
                
                # 2. Fetch History for this Best Section
                # GET /classes/{CourseCode}{SectionName} -> Returns history for ALL terms
                clean_code = course_code.replace(".", "")
                target_url = f"{API_BASE_URL}/{clean_code}{best_section}"
                
                logging.info(f"Fetching details for {course_code} Section {best_section} (Covers {candidate_counts[best_section]} terms)")
                # print(f"  Fetching {course_code} Sec {best_section}...")
                
                history_data = client.make_request(target_url)
                
                # 3. Process the History
                # Extract details for ANY term returned (even if not in our 'uncovered' set, 
                # strictly speaking, but we mainly care about covering the set).
                batch_details = extract_details_from_history(history_data)
                
                # 4. Update Coverage
                # For every term we just got details for, remove from uncovered set
                # AND redundancy check: if we already have details, we can compare (optional).
                for term, details in batch_details.items():
                    if term in uncovered_terms:
                        # Only mark as covered if the fetched history actually matches a term we need
                        # AND the section we fetched actually existed in that term (it should).
                        fetched_details[term] = details
                        uncovered_terms.remove(term)
                    elif term in all_terms_needed:
                        # We already covered this term, but we got data again.
                        # Redundancy check could go here.
                        pass
                
                # 5. Safety Valve
                # If the API call returned NOTHING (empty history?) or didn't cover the terms we expected
                # (e.g. the section exists in "Term Sweep" but "Section History" endpoint is broken/empty),
                # we must remove those terms from `uncovered_terms` to prevent infinite loop,
                # OR remove the `best_section` from consideration for those terms.
                
                # Logic: If `best_section` failed to provide data for a term that supposedly has `best_section`,
                # we remove `best_section` from that term's available list.
                # If a term runs out of available sections, we skip it (logging error).
                
                covered_in_this_pass = set(batch_details.keys())
                
                # Check for terms that SHOULD have been covered (they contain best_section) but WEREN'T
                for term in list(uncovered_terms):
                    if best_section in term_to_sections[term]:
                        if term not in covered_in_this_pass:
                            # The API did not return data for this term/section combination.
                            # Remove this section from consideration for this term.
                            term_to_sections[term].remove(best_section)
                            
                            if not term_to_sections[term]:
                                logging.error(f"Failed to fetch details for {course_code} {term}. No sections left to try.")
                                uncovered_terms.remove(term) # Give up on this term
            
            # C. Write Rows
            # Now we have `fetched_details` map populated as best as possible.
            # Iterate through ALL skeleton sections and write them out.
            for term, sections_list in term_map.items():
                for section_obj in sections_list:
                    # Hydrate with details
                    row = process_section_row(section_obj, fetched_details)
                    writer.writerow(row)

    print(f"\nCatalog scrape complete. Data saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()