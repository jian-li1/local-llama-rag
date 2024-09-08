# Local RAG with Llama 3.1
This project focuses on refining the accuracy and correctness of LLM inferences with web page content as context using a RAG (Retrieval Augmented Generation) approach. The LLM and embedding model used here are Llama 3.1 8B and ``mxbai-embed-large``, respectively, both of which are launched with [Ollama](https://ollama.com). 

This project has three components: the web crawler, the database builder, and the RAG application.

## Crawler
The script ``crawler.py`` is a web crawler that recursively scrapes all child links with the same base URL. It parses the metadata and the page content of each scraped web page to plain text and writes them to a JSON file. Furthermore, the script will also populate a text file containing all the links that it has scraped.

For experimental purposes, the script ``crawler_multi.py`` is also provided. It has the same functionalities as ``crawler.py`` but it is a multithreaded crawler that can scrape web pages concurrently starting from different subdirectories of the same base URL. However, overlaps between multiple crawlers will most likely occur, especially when there are common hyperlinks across all links of the domain (i.e. navigation bars) and all the crawlers start crawling recursively from there.

## Creating the database
The script ``build_database.py`` reads the content of all the JSON files produced by ``crawler.py`` or ``crawler_multi.py`` and inserts them to a Chroma database saved on disk. It splits the page content of each document (web page) into smaller chunks and stores vector embeddings generated by the embedding model for each chunk in the database. For each chunk, a custom embedding ID is assigned in the form of ``https://<some url>.com#<seq num>``, where the sequence number is the ith chunk of the document. All documents begin with a sequence number of 0. The purpose of assigning custom embedding IDs is to know which documents are passed into the LLM during generation and pinpoint exactly which section of each documents it is referring to.

Similar to ``crawler_multi.py``, this program is also multi-thread since Chroma is thread-safe, so it can add multiple documents to the database simultaneously.

## RAG Application
The Jupyter notebook ``local_rag.ipynb`` sets up the entire RAG pipeline and creates the workflow using the LangGraph library. The function ``generate_answer()`` not only returns the generated response but also the chunk IDs that were used for context. 

## Usage
First, download Ollama from this [link](https://ollama.com/download).

To install the LLM and embedding models, run
```
ollama pull llama3.1
ollama pull mxbai-embed-large
```

Next, install the required packages:
```
pip install requirements.txt
```

To start the crawler, run
```
python crawler.py [-h] --url URL --base BASE --out OUT [--depth DEPTH] [--exclude [EXCLUDE ...]] [--no-update]
```
or for the multithreaded crawler, run
```
crawler_multi.py [-h] --url URL [URL ...] --base BASE --out OUT [--depth DEPTH] [--exclude [EXCLUDE ...]] [--no-update]
```
See ``python crawler.py -h`` or ``python crawler_multi.py -h`` for more information about the argument options.

To build the database, run
```
python build_database.py [-h] -d DIR [DIR ...] -o OUT -n NAME [-u]
```
See ``python build_database.py -h`` for more information about the argument options.

Finally, the RAG application can be run under ``local_rag.ipynb``.

## Future Improvements
- I might try to re-implement the crawler with Beautiful Soup or Selenium for more flexibility in what I'm scraping. Currently ``crawler.py`` is relying on LangChain's ``RecursiveURLLoader`` which conveniently parses the web content into text but the library fails to capture HTML content that is loaded dynamically by the web page. 
- I'm thinking of a systematic approach to clean out irrelevant content for each web page. So far, there is still plenty of irrelevant text from navigation bars and sidebars, for example, that is included in the page content, which introduces a lot of noise during inference. 
- I'm still conflicted about adding a condition to perform a web search (if no relevant documents are found) because I want to keep the entire RAG pipeline in a local environment.
- Like many other RAG examples, I might add a final hallucination-checking stage to confirm that the LLM is backing up its answer with only the provided documents.

## Relevant Resources
- [LangChain RecursiveURLLoader](https://python.langchain.com/v0.2/docs/integrations/document_loaders/recursive_url/)
- [Ollama Embedding models](https://ollama.com/blog/embedding-models)
- [LangChain OllamaEmbeddings](https://python.langchain.com/v0.2/docs/integrations/text_embedding/ollama/)
- [LangChain Chroma](https://python.langchain.com/v0.2/docs/integrations/vectorstores/chroma/)
- [LangChain Ollama](https://python.langchain.com/v0.2/docs/integrations/providers/ollama/)
- [LangChaing Ollama Docs](https://api.python.langchain.com/en/latest/llms/langchain_community.llms.ollama.Ollama.html#langchain_community.llms.ollama.Ollama)
- [LangChain Runnable Interface](https://python.langchain.com/v0.1/docs/expression_language/interface/)
- [LangChain RAG Example](https://github.com/langchain-ai/langgraph/blob/main/examples/rag/langgraph_crag_local.ipynb)
