An example of some previous code I wrote that uses the SIS API. This code doesn't cover all of the bases, but it is at least a place to start, and makes clear my `.env` setup.
```python
import requests
import json
import time
from urllib.parse import quote
from dotenv import load_dotenv
import os

def get_api_key():
    """
    Retrieves the JHU SIS API key from an environment variable or user input.
    """
    load_dotenv()
    api_key = os.environ.get("SIS_API_KEY")
    if not api_key:
        print("JHU_API_KEY environment variable not found.")
        try:
            api_key = input("Please enter your JHU SIS API key: ").strip()
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None
    return api_key

def fetch_courses_for_school_and_term(school, term, api_key, session):
    """
    Fetches all course data for a specific school and term.

    Args:
        school (str): The name of the school.
        term (str): The academic term (e.g., "Fall 2025").
        api_key (str): The SIS API key.
        session (requests.Session): The requests session object.

    Returns:
        list: A list of course dictionaries, or None if the request fails.
    """
    # URL encode the school and term names to handle spaces and other special characters
    encoded_school = quote(school)
    encoded_term = quote(term)
    
    url = f"https://sis.jhu.edu/api/classes/{encoded_school}/{encoded_term}?key={api_key}"
    
    try:
        response = session.get(url, timeout=30)
        # Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()
        
        # Check for a specific error message JHU API returns with a 200 status
        # This occurs when no courses are found for the given criteria
        data = response.json()
        if isinstance(data, dict) and data.get('Message') == 'No records found':
            print("  -> No courses found for this term.")
            return []

        return data

    except requests.exceptions.HTTPError as http_err:
        print(f"  -> HTTP error occurred: {http_err} - Status Code: {response.status_code}")
    except requests.exceptions.RequestException as req_err:
        print(f"  -> An error occurred with the request: {req_err}")
    except json.JSONDecodeError:
        print(f"  -> Failed to decode JSON from response. Response text: {response.text[:200]}...")
        
    return None

def main():
    """
    Main function to orchestrate the fetching of all JHU AS/EN course codes.
    """
    api_key = get_api_key()
    if not api_key:
        print("API key is required to proceed. Exiting.")
        return

    # This list contains all terms from Spring 2009 to a year into the future.
    # As per the prompt, you have already generated this list.
    terms = [
      "Fall 2026",
      "Summer 2026",
      "Intersession 2026",
      "Spring 2026",
      "Fall 2025",
      "Summer 2025",
      "Intersession 2025",
      "Spring 2025",
      "Fall 2024",
      "Summer 2024",
      "Spring 2024",
      "Intersession 2024",
      "Fall 2023",
      "Summer 2023",
      "Spring 2023",
      "Intersession 2023",
      "Fall 2022",
      "Summer 2022",
      "Spring 2022",
      "Intersession 2022",
      "Fall 2021",
      "Summer 2021",
      "Spring 2021",
      "Intersession 2021",
      "Fall 2020",
      "Summer 2020",
      "Spring 2020",
      "Intersession 2020",
      "Fall 2019",
      "Summer 2019",
      "Spring 2019",
      "Intersession 2019",
      "Fall 2018",
      "Summer 2018",
      "Spring 2018",
      "Intersession 2018",
      "Fall 2017",
      "Summer 2017",
      "Spring 2017",
      "Intersession 2017",
      "Fall 2016",
      "Summer 2016",
      "Intersession 2016",
      "Spring 2016",
      "Fall 2015",
      "Summer 2015",
      "Intersession 2015",
      "Spring 2015",
      "Fall 2014",
      "Summer 2014",
      "Spring 2014",
      "Intersession 2014",
      "Fall 2013",
      "Summer 2013",
      "Intersession 2013",
      "Spring 2013",
      "Fall 2012",
      "Summer 2012",
      "Spring 2012",
      "Intersession 2012",
      "Fall 2011",
      "Summer 2011",
      "Intersession 2011",
      "Spring 2011",
      "Fall 2010",
      "Summer 2010",
      "Spring 2010",
      "Intersession 2010",
      "Fall 2009",
      "Summer 2009",
      "Spring 2009"
    ]  # curl "https://sis.jhu.edu/api/classes/codes/terms?key="

    schools = [
        "Krieger School of Arts and Sciences",
        "Whiting School of Engineering"
    ]
    
    # Use a set to automatically handle duplicate course codes
    all_course_codes = set()
    
    # Use a requests Session for connection pooling and efficiency
    with requests.Session() as session:
        for school in schools:
            print(f"\n--- Starting school: {school} ---")
            for term in terms:
                print(f"Fetching courses for term: {term}...")
                
                courses = fetch_courses_for_school_and_term(school, term, api_key, session)
                
                if courses is not None:
                    # Extract the 'OfferingName' from each course object
                    for course in courses:
                        if 'OfferingName' in course:
                            all_course_codes.add(course['OfferingName'])
                else:
                    print(f"  -> Skipping term {term} for {school} due to a request error.")

                # Be a good API citizen by waiting briefly between requests
                time.sleep(0.2)

    print("\n-----------------------------------------")
    print("All API requests completed.")

    # Convert the set to a sorted list for consistent output
    sorted_courses = sorted(list(all_course_codes))
    
    output_filename = "jhu_as_en_courses.txt"
    try:
        with open(output_filename, "w") as f:
            for course_code in sorted_courses:
                f.write(f"{course_code}\n")
        print(f"Successfully found {len(sorted_courses)} unique course codes.")
        print(f"Results saved to '{output_filename}'")
    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == "__main__":
    main()
```


[The complete documentation is available here](https://sis.jhu.edu/api)

Their TL;DR 'request patterns' is also attached here for convenience (but the full documentation ***should*** be consulted for anything not obvious from just this):

## Request Patterns

| Request URL Pattern | Description | Notes |
| --- | --- | --- |
| `/classes/codes/schools?key=apikeyvalue` | Returns list of all available schools |  |
| `/classes/codes/terms?key=apikeyvalue` | Returns list of available academic terms |  |
| `/classes/codes/departments/{school name}?key=apikeyvalue` | Returns list of all departments for the {school name} specified |  |
| `/classes/{course number}?key=apikeyvalue` | Returns all offered occurrences of course number* (in available academic terms only) |  |
| `/classes/{course number+section number}?key=apikeyvalue` | Returns all offered occurrences of course number* (in available academic terms only) | Returns section details |
| `/classes/{course number}/{term}?key=apikeyvalue` | Returns all offered occurrences of course number in the academic term specified |  |
| `/classes/{course number+section number}/{term}?key=apikeyvalue` | Returns all offered occurrences of course number in the academic term specified | Returns section details |
| `/classes/{school}?key=apikeyvalue` | Returns all classes for the school specified (in available academic terms only). **Note:** the range for academic terms returned is from Spring 2009 to one year in the future from the current term. |  |
| `/classes/{school}/{term}?key=apikeyvalue` | Returns all classes for the school and academic term specified |  |
| `/classes/{school}/current?key=apikeyvalue` | Returns all classes for the school for the current academic term |  |
| `/classes/{school}/{department}?key=apikeyvalue` | Returns all classes for the school, academic term and department specified |  |
| `/classes/{school}/{department}/{term}?key=apikeyvalue` | Returns all classes for that school for the specified term and department |  |
| `/classes/{school}/{department}/current?key=apikeyvalue` | Returns all classes for that school for the specified department for the current academic term |  |
| `/classes?key=apikeyvalue&param1=paramvalue1&param2=paramvalue2...` | Performs advanced search to include parameters in the query string: `criteria=value`. See Advanced Search for parameters and examples. |  |
### Additional Specifications
* **Course Number Definition:** A course number is defined as (**coursename + section number**) = `ASxxxyyyzz`.
* **Partial Searches:** You can provide a portion of the course number as long as it is at least **3 characters**. In these instances, all courses matching that pattern are returned.
* **Section Details:** To retrieve specific section information, the **full course number and section number** are required.
* **Automatic Detail Retrieval:** When a section number is included in the request, section detail information is automatically returned for each record.
