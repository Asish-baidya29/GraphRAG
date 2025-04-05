# -*- coding: utf-8 -*-
"""GraphRAG - Neo4j.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/15BgXI8969zkSx32HqqiwkNNm2lrYfQfz

##Imports
"""

!pip install --upgrade --quiet langchain langchain-community langchain-experimental langchain-groq langchain-huggingface
!pip install --upgrade --quiet  sentence-transformers
!pip install --upgrade --quiet transformers
!pip install --upgrade --quiet neo4j tiktoken yfiles_jupyter_graphs
!pip install --upgrade --quiet pypdf

"""##Uploading the PDF"""

# Imports
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from google.colab import files
import os

# Upload the PDF file using Google Colab's file upload utility
uploaded = files.upload()

# Get the file path
pdf_path = list(uploaded.keys())[0]

# Load the PDF using Langchain's PyPDFLoader
loader = PyPDFLoader(pdf_path)
documents = loader.load()

type(documents)

documents[0]

len(documents)

"""##Setting up the Environment for Developing

### Environment in a Development Project
In a development project, an **environment** refers to a configured system setup where software is developed, tested, and deployed, often using **environment variables** to manage sensitive information like API keys securely. In **Google Colab**, environment variables can be stored in **secrets** (e.g., `os.environ["API_KEY"] = "your_key"`) to prevent hardcoding sensitive data. This ensures security, flexibility, and easier configuration management across different environments. 🚀
"""

import os
from google.colab import userdata

os.environ["GROQ_API_KEY"] = userdata.get('GROQ_API_KEY')
os.environ["HF_TOKEN"] = userdata.get('HF_TOKEN')
os.environ["NEO4J_URI"] = userdata.get('NEO4J_URI')
os.environ["NEO4J_USERNAME"] = userdata.get('NEO4J_USERNAME')
os.environ["NEO4J_PASSWORD"] = userdata.get('NEO4J_PASSWORD')

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.prompt import PromptTemplate

from typing import Tuple, List, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

from langchain_core.runnables import ConfigurableField

from yfiles_jupyter_graphs import GraphWidget
from neo4j import GraphDatabase

from langchain_community.vectorstores import Neo4jVector
from langchain_community.graphs import Neo4jGraph

from langchain_huggingface import HuggingFaceEmbeddings

try:
  import google.colab
  from google.colab import output
  output.enable_custom_widget_manager()
except:
  pass

from langchain_core.runnables import (
    RunnableBranch,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

"""##Extracting Text from Wikipedia Pages
--Using WikipediaLoader from Langchain
"""

# from langchain.document_loaders import WikipediaLoader
# raw_documents = WikipediaLoader(query="The Merchant of Venice").load()

# len(raw_documents)

# raw_documents[0]

"""##Constants"""

chunk_size = 512
chunk_overlap = 24

model_name = "deepseek-r1-distill-llama-70b"
embedding_model = "sentence-transformers/all-mpnet-base-v2"
temperature = 0.2
tokens_per_minute = 900

"""##Text Splitting using Recursive Charecter Text Splitter"""

# # For Wikipedia
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
# documents = text_splitter.split_documents(raw_documents[:4])

# For PDF (Custom Upload)
from langchain.text_splitter import RecursiveCharacterTextSplitter
text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
document_chunks = text_splitter.split_documents(documents)

#chunks

"""##Initializing a Large Language Model (LLM) and Graph Transformer instance"""

from langchain_groq import ChatGroq

llm = ChatGroq(
            model_name=model_name,
            temperature=temperature,
            max_tokens=None,
            groq_api_key=os.environ["GROQ_API_KEY"],
            timeout=60
        )

# Import the LLMGraphTransformer for converting text into a structured graph
from langchain_experimental.graph_transformers import LLMGraphTransformer

# Initialize the Graph Transformer with a Large Language Model (LLM)
llm_transformer = LLMGraphTransformer(llm=llm)

# Convert a list of textual documents into a structured graph representation
graph_documents = llm_transformer.convert_to_graph_documents(document_chunks)

# The output 'graph_documents' contains entities (nodes) and their relationships (edges),
# which can be used for knowledge graph construction, search, and reasoning.

#graph_documents

# Initializing Neo4j Instance

graph = Neo4jGraph()

from langchain.graphs import Neo4jGraph

graph = Neo4jGraph(
    url="neo4j+s://7e81ff36.databases.neo4j.io",
    username="neo4j",
    #password="your_password"
    password="iJHr03n6VFrBzRpue9uGb6U447teGfKxvUIu6t5x9vU"
)

# Adding the Graph created to the Neo4j Cloud
graph.add_graph_documents(
    graph_documents,
    baseEntityLabel=True, #Ensures nodes have labels like Person, Company, etc.
    include_source=True #Keeps the original document as part of the graph for traceability.
)

# directly show the graph resulting from the given Cypher query
default_cypher = "MATCH (s)-[r:!MENTIONS]->(t) RETURN s,r,t LIMIT 50"

from yfiles_jupyter_graphs import GraphWidget
from neo4j import GraphDatabase

# Visualizing the graph through GraphWidget
def showGraph(cypher: str = default_cypher):
    # create a neo4j session to run queries
    driver = GraphDatabase.driver(
        uri = os.environ["NEO4J_URI"],
        auth = (os.environ["NEO4J_USERNAME"],
                os.environ["NEO4J_PASSWORD"]))
    session = driver.session()
    widget = GraphWidget(graph = session.run(cypher).graph())
    widget.node_label_mapping = 'id'
    display(widget)
    return widget

showGraph()

"""##Creating Word Embedding"""

# Creating Word Embedding instance from HuggingFace
embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'}
        )

from langchain_community.vectorstores import Neo4jVector

# Use the embeddings with Neo4jVector
vector_index = Neo4jVector.from_existing_graph(
    embeddings,
    search_type="hybrid",
    node_label="Document",
    text_node_properties=["text"],
    embedding_node_property="embedding"
)

graph.query("CREATE FULLTEXT INDEX entity IF NOT EXISTS FOR (e:__Entity__) ON EACH [e.id]")

"""##Extracting Entities (Nodes) from the text given input"""

from pydantic import BaseModel, Field
# Extract entities from text
class Entities(BaseModel):
    """Identifying information about entities."""

    names: List[str] = Field(
        ...,
        description="All the person, organization, or business entities that "
        "appear in the text",
    )

# Creating Prompt Templates using Langchain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.prompt import PromptTemplate

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are extracting organization and person entities from the text.",
        ),
        (
            "human",
            "Use the given format to extract information from the following "
            "input: {question}",
        ),
    ]
)

entity_chain = prompt | llm.with_structured_output(Entities)

entity_chain.invoke({"question": "Did Portia had intimate relations with Bassanio?"}).names

"""##Graph Retrieval from the Question"""

# Generates a full-text search query with fuzzy matching (~2) for Neo4j by sanitizing input and combining words using AND.
from langchain_community.vectorstores.neo4j_vector import remove_lucene_chars

def generate_full_text_query(input: str) -> str:
    full_text_query = ""
    words = [el for el in remove_lucene_chars(input).split() if el]
    for word in words[:-1]:
        full_text_query += f" {word}~2 AND"
    full_text_query += f" {words[-1]}~2"
    return full_text_query.strip()

# Full text index query
def structured_retriever(question: str) -> str:
    result = ""
    entities = entity_chain.invoke({"question": question})
    for entity in entities.names:
        response = graph.query(
            """CALL db.index.fulltext.queryNodes('entity', $query, {limit:2})
            YIELD node,score
            CALL {
              WITH node
              MATCH (node)-[r:!MENTIONS]->(neighbor)
              RETURN node.id + ' - ' + type(r) + ' -> ' + neighbor.id AS output
              UNION ALL
              WITH node
              MATCH (node)<-[r:!MENTIONS]-(neighbor)
              RETURN neighbor.id + ' - ' + type(r) + ' -> ' +  node.id AS output
            }
            RETURN output LIMIT 50
            """,
            {"query": generate_full_text_query(entity)},
        )
        result += "\n".join([el['output'] for el in response])
    return result

print(structured_retriever("Did Portia had intimate relations with Bassanio?"))

"""##Combining results from a structured retriever and a vector-based similarity search

"""

# Retrieves structured and unstructured data based on the input question.

def retriever(question: str):
    print(f"Search query: {question}")
    structured_data = structured_retriever(question)
    unstructured_data = [el.page_content for el in vector_index.similarity_search(question)]
    final_data = f"""Structured data:
      {structured_data}
      Unstructured data:
      {"#Document ". join(unstructured_data)}
          """
    return final_data

_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question,
in its original language.
Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""

CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(_template)

def _format_chat_history(chat_history: List[Tuple[str, str]]) -> List:
    buffer = []
    for human, ai in chat_history:
        buffer.append(HumanMessage(content=human))
        buffer.append(AIMessage(content=ai))
    return buffer

_search_query = RunnableBranch(
    # If input includes chat_history, we condense it with the follow-up question
    (
        RunnableLambda(lambda x: bool(x.get("chat_history"))).with_config(
            run_name="HasChatHistoryCheck"
        ),  # Condense follow-up question and chat into a standalone_question
        RunnablePassthrough.assign(
            chat_history=lambda x: _format_chat_history(x["chat_history"])
        )
        | CONDENSE_QUESTION_PROMPT
        | llm
        | StrOutputParser(),
    ),
    # Else, we have no chat history, so just pass through the question
    RunnableLambda(lambda x : x["question"]),
)

template = """Answer the question based only on the following context:
{context}

Question: {question}
Use natural language and be concise.
Answer:"""

prompt = ChatPromptTemplate.from_template(template)

# Creates a processing chain where a search query is retrieved, passed to a prompt, sent to an LLM, and then parsed into a string output.
chain = (
    RunnableParallel(
        {
            "context": _search_query | retriever,
            "question": RunnablePassthrough(),
        }
    )
    | prompt
    | llm
    | StrOutputParser()
)

chain.invoke({"question": "Did Portia had intimate relations with Bassanio?"})

chain.invoke(
    {
        "question": "When was she born?",
        "chat_history": [("Which house did Elizabeth I belong to?", "House Of Tudor")],
    }
)

