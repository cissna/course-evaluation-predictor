import requests
import time
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class APIClient:
    def __init__(self, requests_per_minute=100):
        self.requests_per_minute = requests_per_minute
        self.last_request_time = 0
        self.api_key = os.environ.get("SIS_API_KEY")
        if not self.api_key:
            logging.warning("SIS_API_KEY environment variable not found.")
            # Depending on how strict we want to be, we could prompt here or fail.
            # For now, let's assume it might be set later or passed in params if needed.

    def _send_sms_alert(self, error_message):
        try:
            import sys
            # Add the directory to sys.path temporarily
            sys.path.insert(0, "/Users/isaac.cissna/Desktop/nonrepo/pythonShenanigans/smsTexting")
            # Import the function
            from texting import send_message  # type: ignore
            sys.path.pop(0)  # change directory back
            
            send_message(f"SIS Scraper Paused: Error {error_message}")
            logging.info("SMS alert sent.")
        except Exception as e:
            logging.error(f"Failed to send SMS alert: {e}")

    def _wait_for_rate_limit(self):
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        wait_duration = 60.0 / self.requests_per_minute
        
        if time_since_last_request < wait_duration:
            sleep_time = wait_duration - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()

    def make_request(self, url, params=None, fail_silently=False):
        if params is None:
            params = {}
        
        # Ensure API key is present
        if 'key' not in params and self.api_key:
            params['key'] = self.api_key

        while True:
            self._wait_for_rate_limit()
            
            try:
                response = requests.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return data
                    except ValueError:
                        raise Exception(f"Invalid JSON response: {response.text[:100]}...")
                
                # Logic: If fail_silently is True, only return None for 500 or 404 errors.
                # These suggest a backend issue with that specific query, where fallback is appropriate.
                if fail_silently and response.status_code in [500, 404]:
                    logging.warning(f"Request failed with {response.status_code} (fail_silently=True): {url}")
                    return None
                    
                response.raise_for_status() # Trigger exception for other 4xx/5xx

            except requests.exceptions.HTTPError as e:
                # Handle specific HTTP errors if fail_silently is enabled
                if fail_silently and e.response is not None and e.response.status_code in [500, 404]:
                    logging.warning(f"HTTP Error caught (fail_silently=True): {e}")
                    return None
                
                # Otherwise, treat as a hard failure that needs intervention
                logging.error(f"HTTP Error: {e}")
                self._send_sms_alert(str(e))
                self._pause_and_wait(url, str(e))

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Network errors should NEVER fail silently. We always want to pause and retry.
                logging.error(f"Network error: {e}")
                self._send_sms_alert(str(e))
                self._pause_and_wait(url, str(e))

            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                self._send_sms_alert(str(e))
                self._pause_and_wait(url, str(e))

    def _pause_and_wait(self, url, error_msg):
        print(f"\n[!] Request failed for URL: {url}")
        print(f"[!] Error: {error_msg}")
        print("[!] Execution PAUSED. Enter a new requests_per_minute rate to resume (e.g., '10').")
        
        while True:
            user_input = input("New Rate (req/min): ").strip()
            try:
                new_rate = int(user_input)
                if new_rate > 0:
                    self.requests_per_minute = new_rate
                    logging.info(f"Resuming with rate: {self.requests_per_minute}/min")
                    break
                else:
                    print("Please enter a positive integer.")
            except ValueError:
                print("Invalid input. Please enter an integer.")
