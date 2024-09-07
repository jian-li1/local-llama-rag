from langchain_community.document_loaders.recursive_url_loader import RecursiveUrlLoader
from bs4 import BeautifulSoup as Soup
import argparse
import time
import logging
import json
import os
import threading
from typing import Set

lock = threading.Lock()
total_docs = 0
start = time.time()

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

def start_crawler(i: int, loader: RecursiveUrlLoader, prev_crawled_links: Set[str], crawled_links: Set[str], args):
    global total_docs
    global start
    docs = loader.lazy_load()

    try:
        for doc in docs:
            with lock:
                total_docs += 1
                time_elapsed = time.time() - start
                logger.info(f"{total_docs} -- {total_docs/time_elapsed:.2f} urls/sec -- {doc.metadata['source']} -- Thread {i}")
                
                url = doc.metadata["source"]
                # Prevent duplicate URLs
                if url in crawled_links or url+"/" in crawled_links or (url[-1] == "/" and url[:-1] in crawled_links):
                    logger.info("(Duplicate)")
                # Exclude subdirectories that contain the provided list of strings
                elif args.exclude and any([s in url[len(args.base):] for s in args.exclude]):
                    logger.info("(Skipped)")
                    crawled_links.add(url)
                else:
                    filename = url[len("https://"):].replace("/", "-") if url.startswith("https://") else url.replace("/", "-")
                    doc_dict = {"metadata": doc.metadata, "page_content": doc.page_content}

                    # Write new document to file or update existing document
                    if not url in prev_crawled_links or not args.no_update:
                        with open(f"{args.out}/{filename}.json", "w") as f:
                            json.dump(doc_dict, f, indent=4)
                            crawled_links.add(url)
                    # Append URL to list of crawled URLs
                    if not url in prev_crawled_links:
                        with open(f"{args.out}/urls.txt", "a") as f:
                            f.write(url+"\n")
    except (Exception, KeyboardInterrupt) as e:
        print(repr(e))
    logger.info(f"Thread {i} finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawls websites from the base URL and store all web content into individual JSON files.")
    parser.add_argument("--url", nargs="+", required=True, help="The initial URLs to crawl from")
    parser.add_argument("--base", type=str, required=True, help="The base URL to prevent crawling external links")
    parser.add_argument("--out", type=str, required=True, help="The directory to store the web content")
    parser.add_argument("--depth", type=int, default=2, help="The max depth of the recursive crawling")
    parser.add_argument("--exclude", nargs="*", help="Exclude subdirectories that contain the provided list of strings")
    parser.add_argument("--no-update", action="store_true", help="Do not update previously crawled links")
    args = parser.parse_args()

    print(f"Exclude substrings: {args.exclude}")
    print(f"Update existing documents: {not args.no_update}")

    logging.basicConfig(filename=f"{args.out}/crawler.log", level=logging.INFO, format="%(message)s")
    logger.info(f"Running crawler with {len(args.url)} threads")

    prev_crawled_links = set()
    crawled_links = set()
    if os.path.isfile(f"{args.out}/urls.txt"):
        # Do not append URLs that were already crawled
        with open(f"{args.out}/urls.txt") as f:
            prev_crawled_links = set(f.read().splitlines())
    
    threads = []
    for i, url in enumerate(args.url):
        loader = RecursiveUrlLoader(url=url, base_url=args.base, max_depth=args.depth, extractor=lambda x:Soup(x, "html.parser").text)
        thread = threading.Thread(target=start_crawler, args=(i, loader, prev_crawled_links, crawled_links, args))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    logger.info(f"Finished: {(time.time() - start) / 60:.2f} minutes")
