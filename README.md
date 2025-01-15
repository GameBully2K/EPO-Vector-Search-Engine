# Patent Data Collection, Embedding and indexing using OpenAi embedding model and Cloudflare vectorize db
## Project Team
This project was developed with dedication and expertise by:

**Big thanks to our talented team:**
* MBARKI Bilal ([mbarki.bilal@ensam-casa.ma](mailto:mbarki.bilal@ensam-casa.ma))
* EL ABBADI Abdelbasset 
* ABOUELKACIM Aboubaker
* AOUAME Ali ([aouameali45@gmail.com](mailto:aouameali45@gmail.com))
* OULKAID EL Houssin ([oulkaid.elhoussin@ensam-casa.ma](mailto:oulkaid.elhoussin@ensam-casa.ma))
* EL OUARD Abdel Moula ([abdelmoulaelouard389@gmail.com](mailto:abdelmoulaelouard389@gmail.com))

## Overview
This project implements a system for collecting and analyzing patent data from the European Patent Office (EPO) using their Open Patent Services (OPS) API. The system collects patent abstracts based on keywords, stores them in MongoDB, and creates vector embeddings using OpenAI's API for semantic search capabilities.

## Features
- Patent search using keywords from a CSV file
- Multi-threaded data collection with rate limiting
- MongoDB storage for patent data
- Vector embeddings generation using OpenAI's text-embedding-3-large model
- Vector storage in Cloudflare's Vector Database

## Requirements
- Python 3.8+
- MongoDB running locally
- EPO API credentials
- OpenAI API key
- Cloudflare API key

## Configuration
The system requires the following environment variables:
- `EPO_CONSUMER_KEY`
- `EPO_CONSUMER_SECRET`
- `OPENAI_API_KEY`
- `CLOUDFLARE_API_KEY`

## How It Works
1. The system reads keywords from a CSV file
2. For each keyword, it searches patents using the EPO API
3. Patent abstracts are collected and stored in MongoDB
4. The embeddeAndStore.py script generates vector embeddings
5. Embeddings are stored in Cloudflare's Vector Database for future similarity searches
