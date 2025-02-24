import os
from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from supabase import create_client, Client
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", "")
)

def load_and_split_pdf(file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict]:
    """
    Load PDF and split into chunks using LangChain
    """
    # Load PDF
    loader = PyPDFLoader(file_path)
    pages = loader.load()
    
    # Initialize text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    # Split documents
    chunks = text_splitter.split_documents(pages)
    
    # Process chunks into desired format
    processed_chunks = []
    for i, chunk in enumerate(chunks):
        processed_chunks.append({
            "content": chunk.page_content,
            "metadata": {
                "page": chunk.metadata.get("page", 0),
                "source": file_path,
                "chunk_index": i
            }
        })
    
    return processed_chunks

def generate_embeddings(chunks: List[Dict]) -> List[Dict]:
    """
    Generate embeddings for chunks using OpenAI
    """
    embeddings = OpenAIEmbeddings()
    
    for chunk in chunks:
        vector = embeddings.embed_query(chunk["content"])
        chunk["embedding"] = vector
    
    return chunks

def batch(iterable, n=1):
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]

def insert_into_supabase(chunks: List[Dict]) -> None:
    """
    Insert chunks and their embeddings into Supabase
    """
    data = [{
            "content": chunk["content"],
            "metadata": chunk["metadata"],
            "embedding": chunk["embedding"]
        } for chunk in chunks]
    
    for i, selected_data in enumerate(batch(data, 1000)):
        supabase.table("documents").insert(selected_data).execute()
        logger.info(f"Inserted chunks {i*1000} to {i*1000+len(selected_data)}")
    logger.info(f"Done inserting chunks {len(data)}")


def process_pdf(file_path: str) -> None:
    """
    Main function to process PDF and store in Supabase
    """
    # Load and split PDF
    chunks = load_and_split_pdf(file_path)
    print(f"Created {len(chunks)} chunks")
    
    # Generate embeddings
    chunks_with_embeddings = generate_embeddings(chunks)
    print("Generated embeddings")
    
    # Insert into Supabase
    insert_into_supabase(chunks_with_embeddings)
    print("Completed insertion into Supabase")

if __name__ == "__main__":
    # Example usage
    pdf_path = '../data/Archive.pdf'
    process_pdf(pdf_path)