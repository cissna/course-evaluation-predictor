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
                
                # If fail_silently is True, we return None on non-200 to let caller handle it (e.g. switch strategy)
                if fail_silently:
                    logging.warning(f"Request failed silently (Status {response.status_code}): {url}")
                    return None
                    
                response.raise_for_status() # Trigger exception for 4xx/5xx

            except Exception as e:
                if fail_silently:
                    logging.warning(f"Request failed silently: {e}")
                    return None
                    
                logging.error(f"Request failed: {e}")
                self._send_alert_email(str(e))
                self._send_sms_alert(str(e))
                
                print(f"\n[!] Request failed for URL: {url}")
                print(f"[!] Error: {e}")
                print("[!] Execution PAUSED. Enter a new requests_per_minute rate to resume (e.g., '10').")
