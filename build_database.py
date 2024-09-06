from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings.ollama import OllamaEmbeddings
from langchain.schema import Document
from typing import List
from tqdm import tqdm
import argparse
import os
import json
import time
import threading
import re

num_threads = 6
embeddings = OllamaEmbeddings(model="mxbai-embed-large", num_thread=num_threads)

# Initialize a text splitter with specified chunk size and overlap
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=500, chunk_overlap=250
)

def assign_chunk_id(chunks: List[Document]):
    last_source = None
    current_chunk_idx = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        if not source:
            continue

        # If source is same as the last one, increment the index
        if source == last_source:
            current_chunk_idx += 1
        else:
            current_chunk_idx = 0
        
        # Calculate chunk ID
        chunk_id = f"{source}#{current_chunk_idx}"
        last_source = source

        # Add chunk ID to metadata
        chunk.metadata["id"] = chunk_id

def upsert_doc(doc: Document, update: bool):
    # Split document into chunks and assign an embedding ID for each of them
    chunks = text_splitter.split_documents([doc])
    assign_chunk_id(chunks)

    existing_items = db.get(ids=[chunk.metadata["id"] for chunk in chunks], include=[])
    existing_ids = set(existing_items["ids"])

    new_chunks = []
    new_chunk_ids = []
    update_chunks = []
    update_chunk_ids = []

    for chunk in chunks:
        # New chunk
        if not chunk.metadata["id"] in existing_ids:
            new_chunks.append(chunk)
            new_chunk_ids.append(chunk.metadata["id"])
        # Chunk already exists
        elif update:
            update_chunks.append(chunk)
            update_chunk_ids.append(chunk.metadata["id"])
    
    # Add new chunks
    if len(new_chunks) > 0:
        db.add_documents(documents=new_chunks, ids=new_chunk_ids)
    # Update existing chunks
    if len(update_chunks) > 0:
        db.update_documents(documents=update_chunks, ids=update_chunk_ids)
    
    chunks.clear()
    new_chunks.clear()
    new_chunk_ids.clear()
    update_chunks.clear()
    update_chunk_ids.clear()

def process_documents(json_files: List[str], update: bool):
    json_files = tqdm(json_files, dynamic_ncols=True, total=len(json_files), leave=False)
    
    bad_files = 0
    processed_files = 0
    # json_files.set_postfix_str(f"Added: {processed_files}, Failed: {bad_files}")
    for file in json_files:
        json_files.set_postfix_str(f"Added: {processed_files}, Failed: {bad_files}, File: {file}")

        with open(file) as f:
            data = json.load(f)
        if (metadata := data.get("metadata")) and (content := data.get("page_content")) and not None in metadata.values():
            # Remove newlines and tabs
            content = re.sub(r"\n\n+ *", "\n\n", content)
            content = re.sub(r"\t\t*", " ", content)

            doc = Document(metadata=metadata, page_content=content)
            upsert_doc(doc, update)
            processed_files += 1
        else:
            bad_files += 1
        
        json_files.set_postfix_str(f"Added: {processed_files}, Failed: {bad_files}, File: {file}")
        del metadata, content, doc, data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reads a list of JSON files in the form of a LangChain Document (containing the keys \"metadata\" and \"page_content\")\
              and appends their content into a Chroma Database."
    )
    parser.add_argument("-d", "--dir", nargs="+", required=True, help="The directory or directories to read JSON files from")
    parser.add_argument("-o", "--out", type=str, required=True, help="The name of the Chroma database directory")
    parser.add_argument("-n", "--name", type=str, required=True, help="Specify collection name")
    parser.add_argument("-u", "--update", action="store_true", help="Updates existing documents")
    args = parser.parse_args()

    print(f"Existing documents will {'' if args.update else 'not '}be updated")

    db = Chroma(persist_directory=args.out, embedding_function=embeddings, collection_name=args.name)

    for dir in args.dir:
        print(f"Inserting documents from {dir} to collection '{args.name}'")
        # Get all JSON files in the directory
        json_files = [os.path.join(dir, filename) for filename in os.listdir(dir) if filename.endswith(".json")]

        num_threads = 1 if len(json_files) < 6 else 6

        # Split files evenly across all threads
        chunk_size = len(json_files) // num_threads
        file_chunks = [json_files[i:i + chunk_size] for i in range(0, len(json_files), chunk_size)]

        start_time = time.time()
        threads = []
        # Start each thread
        for chunk in file_chunks:
            thread = threading.Thread(target=process_documents, args=(chunk, args.update))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
        
        print(f"Total time: {(time.time() - start_time) / 60:.2f} minutes")