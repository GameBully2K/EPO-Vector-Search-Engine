import os
from openai import OpenAI
import pymongo
from cloudflare import Cloudflare
import json
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "patent_db"
COLLECTION_NAME = "patents"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY")
CLOUDFLARE_ACCOUNT_ID = "f4949f4978f7753e29da78b4938cd8bc"
CLOUDFLARE_INDEX_NAME = "easy-patent"
CLOUDFLARE_ENDPOINT = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/vectorize/indexes/{CLOUDFLARE_INDEX_NAME}/insert"
MAX_THREADS = 20  # Number of threads for concurrent processing

client = OpenAI(api_key=OPENAI_API_KEY)
cf_client = Cloudflare(
    api_email="gdgoc.uh2@gmail.com",
    api_key=CLOUDFLARE_API_KEY
)
# Initialize OpenAI client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def get_abstracts_from_mongodb() -> List[Dict]:
    """Fetch abstracts from MongoDB."""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        abstracts = list(collection.find({}, {"_id": 0, "patentNumber": 1, "abstract": 1}))
        logger.info(f"Fetched {len(abstracts)} abstracts from MongoDB.")
        return abstracts
    except Exception as e:
        logger.error(f"Error fetching abstracts from MongoDB: {str(e)}")
        return []

def embed_abstract(abstract: Dict) -> Dict:
    """Embed a single abstract using OpenAI's text-embedding-3-large model."""
    try:
        logger.info(f"Embedding abstract for patent: {abstract['patentNumber']}")
        response = client.embeddings.create(input=abstract["abstract"],
        model="text-embedding-3-large",
        dimensions=1536)
        embedding = response.data[0].embedding
        logger.info(f"Successfully embedded abstract for patent: {abstract['patentNumber']}")
        return {
            "patentNumber": abstract["patentNumber"],
            "embedding": embedding
        }
    except Exception as e:
        logger.error(f"Error embedding abstract for patent {abstract['patentNumber']}: {str(e)}")
        return None

def store_embedding_in_cloudflare(embedded_abstract: Dict) -> bool:
    """Store a single embedding in Cloudflare's Vector DB."""
    try:
        body = {
            "vectors": [
                {
                    "id": embedded_abstract["patentNumber"],
                    "values": embedded_abstract["embedding"]
                }
            ]
        }
        
        response = cf_client.vectorize.indexes.insert(
            index_name=CLOUDFLARE_INDEX_NAME,
            account_id=CLOUDFLARE_ACCOUNT_ID,
            body=json.dumps(body).encode('utf-8')
        )
        
        if response.get('success', False):
            logger.info(f"Successfully stored embedding for patent: {embedded_abstract['patentNumber']}")
            return True
        else:
            logger.error(f"Failed to store embedding for patent {embedded_abstract['patentNumber']}")
            return False
            
    except Exception as e:
        logger.error(f"Error storing embedding for patent {embedded_abstract['patentNumber']}: {str(e)}")
        return False

def process_abstract(abstract: Dict) -> None:
    """Process a single abstract: embed and store it."""
    embedded_abstract = embed_abstract(abstract)
    if embedded_abstract:
        store_embedding_in_cloudflare(embedded_abstract)

def main():
    # Step 1: Fetch abstracts from MongoDB
    abstracts = get_abstracts_from_mongodb()
    if not abstracts:
        logger.error("No abstracts found in MongoDB. Exiting.")
        return

    # Step 2: Process abstracts concurrently using multi-threading
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(process_abstract, abstract) for abstract in abstracts]
        for future in as_completed(futures):
            try:
                future.result()  # Check for exceptions in threads
            except Exception as e:
                logger.error(f"Error in thread: {str(e)}")

    logger.info("Processing completed!")

if __name__ == "__main__":
    main()