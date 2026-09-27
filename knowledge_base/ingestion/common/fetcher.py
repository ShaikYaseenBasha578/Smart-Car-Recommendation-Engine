import requests
import time
import random

def fetch_model_page(make_slug, model_slug, max_retries=3):
    url = f"https://www.91wheels.com/cars/{make_slug}/{model_slug}"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    
    for attempt in range(max_retries):
        try:
            # Polite rate limiting + jitter
            time.sleep(1.5 + random.random()) 
            r = requests.get(url, headers=headers, timeout=15)
            
            if r.status_code == 200:
                return r.text, r.status_code, url
            elif r.status_code in [404, 403]:
                # Don't retry on definite failures
                print(f"Fetch {url} returned {r.status_code}, aborting.")
                return None, r.status_code, url
            else:
                print(f"Fetch {url} returned {r.status_code}, retrying...")
                
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            
        time.sleep(2 ** attempt) # Exponential backoff
        
    return None, None, url
