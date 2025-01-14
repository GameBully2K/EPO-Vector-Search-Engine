import requests
import csv
import os
from pymongo import MongoClient
import time
from typing import List, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
import logging
import json  # Add this import at the top

# Configuration
CONSUMER_KEY = os.getenv("EPO_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("EPO_CONSUMER_SECRET")
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "patent_db"
COLLECTION_NAME = "patents"
MAX_THREADS = 20
RATE_LIMIT_DELAY = 0  # 500ms between requests per thread

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)

class RateLimiter:
    def __init__(self, calls_per_second: float):
        self.delay = 1.0 / calls_per_second
        self.last_call = {}
        self._lock = threading.Lock()

    def wait(self):
        thread_id = threading.get_ident()
        with self._lock:
            if thread_id in self.last_call:
                elapsed = time.time() - self.last_call[thread_id]
                if elapsed < self.delay:
                    time.sleep(self.delay - elapsed)
            self.last_call[thread_id] = time.time()

def get_oauth_token(consumer_key: str, consumer_secret: str) -> str:
    url = "https://ops.epo.org/3.2/auth/accesstoken"  # EPO OAuth endpoint
    try:
        data = {"grant_type": "client_credentials"}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(url, data=data, auth=(consumer_key, consumer_secret), headers=headers)
        resp.raise_for_status()
        data = resp.json()
        print(f"OAuth token obtained: {data['access_token']}")
        return data["access_token"]
    except Exception as e:
        logging.error(f"Failed to obtain OAuth token: {str(e)}")
        return ""

class EPOClient:
    def __init__(self, consumer_key: str, consumer_secret: str):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token = get_oauth_token(consumer_key, consumer_secret)
        self.token_acquired_time = time.time()
        self.token_valid_for = 20 * 60  # 20 minutes in seconds
        
        self.base_url = "https://ops.epo.org/3.2/rest-services"
        self.headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }

    def ensure_token(self):
        # If token is about to expire in ~1 minute, refresh
        if (time.time() - self.token_acquired_time) >= (self.token_valid_for - 60):
            self.token = get_oauth_token(self.consumer_key, self.consumer_secret)
            self.headers['Authorization'] = f'Bearer {self.token}'
            self.token_acquired_time = time.time()

    def search_patents(self, keyword: str) -> Dict:
        self.ensure_token()
        # Use URL-safe encoding for the keyword
        from urllib.parse import quote
        encoded_keyword = quote(f"ti={keyword}")
        endpoint = f"{self.base_url}/published-data/search?Range=1-100&q={encoded_keyword}"
        
        print(f"\nRequesting URL: {endpoint}")
        print(f"Headers: {self.headers}")
        
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            print(f"Response status code: {response.status_code}")
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Error fetching data for keyword '{keyword}': {str(e)}")
            print(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            return None

    def get_abstract(self, patent_number: str, patent_type: str) -> Dict:
        self.ensure_token()
        endpoint = f"{self.base_url}/published-data/publication/{patent_type}/{patent_number}/abstract"
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            abstract = (data.get("ops:world-patent-data", {})
                    .get("exchange-documents", {})
                    .get("exchange-document", {})
                    .get("abstract", {})
                    .get("p", {})
                    .get("$", "No abstract available"))
            
            return {
                "patentNumber": patent_number,
                "abstract": abstract
            }
        except requests.RequestException as e:
            logging.error(f"Error fetching abstract for patent {patent_number}: {str(e)}")
            return {
                "patentNumber": patent_number,
                "abstract": "Abstract fetch failed"
            }

def process_keyword(epo_client: EPOClient, keyword: str, collection) -> None:
    results = epo_client.search_patents(keyword)
    abstracts = []
    
    if not results:
        return

    try:
        patent_docs = (results.get("ops:world-patent-data", {})
                    .get("ops:biblio-search", {})
                    .get("ops:search-result", {})
                    .get("ops:publication-reference", []))
        
        if not patent_docs:
            return

        logging.info(f"\nProcessing patents for keyword '{keyword}':")
        for doc in patent_docs[:100]:  # Get up to 100 patents per keyword
            doc_id = doc.get("document-id", {})
            country = doc_id.get("country", {}).get("$", "")
            number = doc_id.get("doc-number", {}).get("$", "")
            kind = doc_id.get("kind", {}).get("$", "")
            patent_number = f"{country}{number}{kind}"
            patent_type = doc_id.get("@document-id-type", "")
            
            # Get abstract for each patent
            abstract_data = epo_client.get_abstract(patent_number, patent_type)
            collection.insert_one(abstract_data)
            
            logging.info(f"Processed patent: {patent_number}")
            
    except Exception as e:
        logging.error(f"Error processing results for keyword '{keyword}': {str(e)}")

def read_first_n_keywords(file_path: str, n: int = 20) -> List[str]:
    keywords = set()
    try:
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if row and len(keywords) < n:
                    keywords.add(row[0].strip().lower())
        return list(keywords)
    except Exception as e:
        logging.error(f"Error reading keywords file: {str(e)}")
        return []

def main():
    # Initialize client
    epo_client = EPOClient(CONSUMER_KEY, CONSUMER_SECRET)
    
    # Read first 20 keywords
    keywords = read_first_n_keywords("keywords.csv", 1000)
    
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    logging.info(f"Starting processing with {len(keywords)} keywords...")
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(process_keyword, epo_client, kw, collection) for kw in keywords]
        for future in as_completed(futures):
            if future.exception():
                logging.error(f"Error in thread: {str(future.exception())}")

    logging.info(f"\nProcessing completed!")

if __name__ == "__main__":
    main()
