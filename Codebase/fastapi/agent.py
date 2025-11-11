# from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
import requests
from tavily import TavilyClient  # For web search
from graphviz import Digraph  # For generating mind maps
from openai import OpenAI
import os
from typing import List
from typing import Dict
import boto3
import whisper
import tempfile
import html
import re
import json
import xmltodict
from io import StringIO
import xml.etree.ElementTree as ET
from lxml import etree
from graphviz import Digraph
from nltk.tokenize import sent_tokenize
import nltk
nltk.download('punkt')
nltk.download('stopwords')

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_core.tools import tool
from langchain_core.agents import AgentAction
from langchain_core.messages import BaseMessage

from typing import TypedDict, Annotated
import operator


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Configuration
# Environment variables
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "default_pinecone_api_key")  # Provide a default for local testing
INDEX_NAME = os.getenv("INDEX_NAME", "ted-talks-index")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "default_tavily_api_key")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "default_aws_access_key_id")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "default_aws_secret_access_key")
S3_BUCKET = os.getenv("S3_BUCKET", "default_bucket_name")


class AgentState(TypedDict):
    input: str
    chat_history: list[BaseMessage]
    intermediate_steps: Annotated[list[tuple[AgentAction, str]], operator.add]




# Initialize clients
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
s3_client = boto3.client(
    "s3",
    region_name="us-east-1",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

def initialize_pinecone():
    return Pinecone(api_key=PINECONE_API_KEY)

pinecone_client = initialize_pinecone()

def get_index():
    if INDEX_NAME not in [idx.name for idx in pinecone_client.list_indexes()]:
        raise ValueError(f"Index '{INDEX_NAME}' does not exist. Ensure the index is created.")
    return pinecone_client.Index(INDEX_NAME)

def create_query_embedding(query: str):
    embedding_model = OpenAIEmbeddings(model=EMBEDDING_MODEL, openai_api_key=OPENAI_API_KEY)
    return embedding_model.embed_query(query)

client = OpenAI()

def query_openai(prompt: str, model: str = "gpt-4o") -> str:
    """
    Query the OpenAI GPT model using the new OpenAI client for chat completion.

    Args:
        prompt (str): The prompt text to provide to the OpenAI model.
        model (str): The OpenAI model to use for the query.

    Returns:
        str: The response from the OpenAI model.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            max_completion_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error querying OpenAI: {str(e)}"




def fetch_metadata_from_s3(bucket_name: str, slug: str) -> dict:
    try:
        s3_key = f"{slug.strip()}/metadata.json"  # Ensure no trailing spaces
        print(f"Fetching metadata from S3 with key: {s3_key}")  # Debug
        response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        metadata = json.loads(response['Body'].read().decode('utf-8'))
        return metadata
    except s3_client.exceptions.NoSuchKey:
        print(f"Key not found: {slug}")
        raise RuntimeError(f"No metadata found for {slug}")
    except Exception as e:
        raise RuntimeError(f"Error fetching metadata from S3: {e}")



def extract_slug_from_url(url: str) -> str:
    """
    Extract the slug from a TED Talk URL.
    Example: https://www.ted.com/talks/sting_how_i_started_writing_songs_again -> sting_how_i_started_writing_songs_again
    """
    if not url.startswith("https://www.ted.com/talks/"):
        raise ValueError("Invalid TED Talk URL")
    return url.split("https://www.ted.com/talks/")[1]

def chatbot_agent(url: str, question: str) -> str:
    """
    Answer a question about a TED Talk based on its metadata fetched from S3.
    """
    try:
        slug = extract_slug_from_url(url)
    except ValueError as e:
        return str(e)

    metadata = fetch_metadata_from_s3(S3_BUCKET, slug)
    if "error" in metadata:
        return metadata["error"]

    prompt = (
        f"The following metadata is provided for a TED Talk:\n\n"
        f"Title: {metadata.get('title', 'N/A')}\n"
        f"Speaker(s): {metadata.get('speakers', 'N/A')}\n"
        f"URL: {metadata.get('url', 'N/A')}\n"
        f"Transcript: {metadata.get('transcript', 'N/A')}\n\n"
        f"Please answer the following question based solely on the information above:\n\n"
        f"Question: {question}\n"
        f"Answer:"
    )
    return query_openai(prompt)

# Fetch Video URL
def fetch_video_url(webpage_url):
    """
    Fetch the embed HTML for a TED Talk video from its URL.
    """
    try:
        if not webpage_url.startswith("https://www.ted.com/talks/"):
            raise ValueError("Invalid TED Talk URL")
        oembed_url = f"https://www.ted.com/services/v1/oembed.json?url={webpage_url}"
        response = requests.get(oembed_url)
        response.raise_for_status()
        return response.json().get("html")
    except Exception as e:
        print(f"Error fetching video embed URL for {webpage_url}: {e}")
        return None

# Search TED Talks
def search_talks_agent(query: str):
    """
    Search TED Talks using Pinecone based on a query and return metadata of top matches.
    """
    try:
        index = get_index()
        query_embedding = create_query_embedding(query)
        search_results = index.query(
            vector=query_embedding,
            top_k=6,
            include_metadata=True,
            namespace="ted-talks"
        )
        if not search_results or not search_results.get("matches"):
            return {"query": query, "results": []}

        talks = []
        for match in search_results["matches"]:
            metadata = match["metadata"]
            talk_url = metadata.get("url", "")
            video_embed_html = fetch_video_url(talk_url)
            talks.append({
                "title": metadata.get("title", "N/A"),
                "description": metadata.get("description", "Description not available"),
                "speaker": metadata.get("speakers", "Speaker not available"),
                "slug": extract_slug_from_url(talk_url),  # Include the slug
                "talk_url": talk_url,
                "video_embed_html": video_embed_html,
            })
        return {"query": query, "results": talks}
    except Exception as e:
        return {"error": str(e)}

def get_trending_talks_agent(top_k: int = 5) -> List[dict]:
    """
    Fetch the top trending TED Talks from Pinecone.

    Args:
        top_k (int): Number of top trending TED Talks to fetch. Default is 5.

    Returns:
        List[dict]: A list of dictionaries representing trending TED Talks.
    """
    try:
        # Access the Pinecone index
        index = get_index()

        # Query the Pinecone index to retrieve top talks
        search_results = index.query(
            vector=[0] * 1536,  # Use a neutral vector for general top results
            top_k=top_k,
            include_metadata=True,
            namespace="ted-talks"
        )

        if not search_results or not search_results.get("matches"):
            return []

        talks = []
        for match in search_results["matches"]:
            metadata = match["metadata"]
            talk_url = metadata.get("url", "")
            video_embed_html = fetch_video_url(talk_url)
            talks.append({
                "title": metadata.get("title", "N/A"),
                "description": metadata.get("description", "Description not available"),
                "speaker": metadata.get("speakers", "Speaker not available"),
                "slug": extract_slug_from_url(talk_url),
                "talk_url": talk_url,
                "video_embed_html": video_embed_html,
            })

        return talks
    except Exception as e:
        raise RuntimeError(f"Error retrieving trending talks: {e}")




@tool("qa_agent")
def qa_agent_tool(talk_url: str, question: str) -> str:
    """
    Handles open-ended questions for a specific TED Talk using its metadata.

    Args:
        talk_url (str): The URL of the TED Talk.
        question (str): The open-ended question to answer based on the TED Talk metadata.

    Returns:
        str: The answer to the question.
    """
    try:
        slug = extract_slug_from_url(talk_url)
        metadata = fetch_metadata_from_s3(S3_BUCKET, slug)

        if not metadata:
            return f"No metadata found for the TED Talk at URL: {talk_url}"

        prompt = (
            f"The following metadata is provided for a TED Talk:\n\n"
            f"Title: {metadata.get('title', 'N/A')}\n"
            f"Speaker(s): {metadata.get('speakers', 'N/A')}\n"
            f"URL: {metadata.get('url', 'N/A')}\n"
            f"Transcript: {metadata.get('transcript', 'N/A')}\n\n"
            f"Please answer the following open-ended question based on the information above:\n\n"
            f"Question: {question}\n"
            f"Answer:"
        )
        return query_openai(prompt)
    except Exception as e:
        return f"Error in QA Agent: {e}"





@tool("compare_agent")
def compare_agent_tool(talk1_url: str, talk2_url: str) -> str:
    """
    Compares two TED Talks, highlighting similarities and differences.

    Args:
        talk1_url (str): The URL of the first TED Talk.
        talk2_url (str): The URL of the second TED Talk.

    Returns:
        str: A structured comparison report.
    """
    try:
        metadata1 = fetch_metadata_from_s3(S3_BUCKET, extract_slug_from_url(talk1_url))
        metadata2 = fetch_metadata_from_s3(S3_BUCKET, extract_slug_from_url(talk2_url))

        if not metadata1 or not metadata2:
            return "Error fetching metadata for one or both TED Talks."

        prompt = (
            f"Compare the following two TED Talks:\n\n"
            f"TED Talk 1:\n"
            f"Title: {metadata1.get('title', 'N/A')}\n"
            f"Speaker(s): {metadata1.get('speakers', 'N/A')}\n"
            f"Transcript Summary: {summarize_transcript(metadata1.get('transcript', 'N/A'))}\n\n"
            f"TED Talk 2:\n"
            f"Title: {metadata2.get('title', 'N/A')}\n"
            f"Speaker(s): {metadata2.get('speakers', 'N/A')}\n"
            f"Transcript Summary: {summarize_transcript(metadata2.get('transcript', 'N/A'))}\n\n"
            f"Provide a detailed comparison including common themes, key differences, and unique highlights."
        )
        return query_openai(prompt)
    except Exception as e:
        return f"Error in Compare Agent: {e}"



@tool("web_search_agent")
def web_search_tool(query: str) -> str:
    """
    Uses Tavily to perform web searches and generates contextual responses for open-ended questions.

    Args:
        query (str): The open-ended query to search and summarize.

    Returns:
        str: The contextual response based on the search results.
    """
    try:
        response = tavily_client.search(query, limit=3)
        results = response.get("results", [])

        if not results:
            return "No relevant results found."

        extracted_data = [
            f"Title: {res.get('title', 'No Title')}\nURL: {res.get('url', 'No URL')}\nContent: {res.get('content', 'No Content Available')}"
            for res in results
        ]
        combined_content = "\n\n".join(extracted_data)

        prompt = (
            f"Based on the following search results, generate a concise and detailed response to the query '{query}':\n\n"
            f"{combined_content}"
        )
        return query_openai(prompt)
    except Exception as e:
        return f"Error in Web Search Tool: {e}"







class RoutingOracle:
    def __init__(self):
        self.routes = {
            "qa_agent": qa_agent_tool,
            "compare_agent": compare_agent_tool,
            "web_search_agent": web_search_tool,
        }

    def decide_route(self, query: str) -> str:
        """
        Decides which tool to route the query to based on keywords in the query.
        """
        if "compare" in query.lower():
            return "compare_agent"
        elif "in" in query.lower():  # QA tool assumption: "What does X talk about in Y?"
            return "qa_agent"
        else:
            return "web_search_agent"

    def execute(self, tool_name: str, inputs: dict) -> str:
        """
        Executes the appropriate tool with the given inputs.
        """
        tool_function = self.routes.get(tool_name)
        if tool_function:
            return tool_function(**inputs)
        return "No suitable tool found."


routing_oracle = RoutingOracle()




def generate_transcript(slug_or_title: str) -> str:
    """
    Retrieve the raw transcript for a TED Talk from metadata in S3, process it with OpenAI,
    and return a clean, paragraphed transcript output.

    Args:
        slug_or_title (str): The slug or title of the TED Talk.

    Returns:
        str: The cleaned and paragraphed transcript.
    """
    # Fetch metadata from S3
    metadata = fetch_metadata_from_s3(S3_BUCKET, slug_or_title)
    if "error" in metadata:
        raise ValueError(metadata["error"])

    # Retrieve the raw transcript
    raw_transcript = metadata.get("transcript", "")
    if not raw_transcript:
        raise ValueError("Transcript not found in metadata.")

    # Prepare the OpenAI query to process the transcript
    try:
        prompt = (
            "The following is a raw transcript of a TED Talk. "
            "Please format it into clean paragraphs with proper punctuation, "
            "and ensure that quotes and apostrophes are handled correctly. "
            "Preserve the original meaning and structure:\n\n"
            f"{raw_transcript}\n\n"
            "Return the cleaned transcript:"
        )

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert at formatting transcripts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1500,
        )

        cleaned_transcript = response.choices[0].message.content.strip()
        return cleaned_transcript

    except Exception as e:
        raise RuntimeError(f"Error processing transcript with OpenAI: {e}")



def get_related_talks_agent(slug: str) -> list:
    """
    Fetch related TED Talks based on the slug of the selected TED Talk.

    Args:
        slug (str): The slug of the selected TED Talk.

    Returns:
        list: A list of dictionaries representing related TED Talks.
    """
    try:
        # Fetch metadata for the selected talk using its slug
        metadata = fetch_metadata_from_s3(S3_BUCKET, slug)
        if "error" in metadata:
            raise ValueError(metadata["error"])

        # Use the title of the talk as the query
        title = metadata.get("title", "")
        if not title:
            raise ValueError("Title not found in metadata.")

        # Perform a search using the title to find related talks
        search_results = search_talks_agent(title)

        # Exclude the current talk from the results
        related_talks = [
            talk for talk in search_results.get("results", [])
            if talk["slug"] != slug
        ]

        return related_talks[:3]  # Return the top 3 related talks
    except Exception as e:
        raise RuntimeError(f"Error fetching related talks: {e}")



def web_search_agent(query: str) -> str:
    """
    Search the web using Tavily, retrieve the top 3 results, and generate a summary using OpenAI.
    """
    try:
        # Fetch search results from Tavily
        response = tavily_client.search(query, limit=3)
        print(f"Raw response from Tavily: {response}")  # Debugging

        # Ensure response contains 'results'
        results = response.get("results", [])
        if not isinstance(results, list) or len(results) == 0:
            raise ValueError("No relevant results found in the Tavily response")

        # Extract titles, URLs, and content
        extracted_data = []
        for result in results[:3]:  # Top 3 results
            title = result.get("title", "No Title")
            url = result.get("url", "No URL")
            content = result.get("content", "No Content Available")
            extracted_data.append(f"Title: {title}\nURL: {url}\nContent: {content}\n")

        # Combine extracted content
        combined_content = "\n\n".join(extracted_data)

        # Create a prompt for summarization
        prompt = (
            f"The following information has been retrieved for the query '{query}':\n\n"
            f"{combined_content}\n\n"
            "Generate a concise summary of this information:"
        )

        # Use OpenAI to generate a summary
        summary = query_openai(prompt)
        return summary

    except Exception as e:
        return f"Error processing web search and summarization: {e}"


def summarize_transcript(transcript: str) -> str:
    """
    Summarize a long transcript using OpenAI.
    """
    if len(transcript.split()) > 1000:  # Adjust the length threshold as needed
        prompt = (
            f"The following is a long transcript from a TED Talk. Summarize it in under 500 words:\n\n{transcript}"
        )
        summary = query_openai(prompt)
        return summary
    return transcript


def compare_talks_agent(talk1_slug: str, talk2_slug: str) -> dict:
    """
    Compare two TED Talks by fetching their metadata from S3 and generating a clean text report.
    """
    try:
        # Fetch metadata for both talks
        metadata1 = fetch_metadata_from_s3(S3_BUCKET, talk1_slug)
        metadata2 = fetch_metadata_from_s3(S3_BUCKET, talk2_slug)

        # Check for errors in metadata fetching
        if "error" in metadata1:
            return {"error": f"Error fetching metadata for Talk 1: {metadata1['error']}"}
        if "error" in metadata2:
            return {"error": f"Error fetching metadata for Talk 2: {metadata2['error']}"}

        # Summarize transcripts if necessary
        metadata1["transcript"] = summarize_transcript(metadata1.get("transcript", ""))
        metadata2["transcript"] = summarize_transcript(metadata2.get("transcript", ""))

        # Construct the prompt for OpenAI
        prompt = (
            f"Compare the following two TED Talks based on their metadata:\n\n"
            f"Ted Talk 1:\n"
            f"Title: {metadata1.get('title', 'N/A')}\n"
            f"Speaker(s): {metadata1.get('speakers', 'N/A')}\n"
            f"Transcript Summary: {metadata1.get('transcript', 'N/A')}\n\n"
            f"Ted Talk 2:\n"
            f"Title: {metadata2.get('title', 'N/A')}\n"
            f"Speaker(s): {metadata2.get('speakers', 'N/A')}\n"
            f"Transcript Summary: {metadata2.get('transcript', 'N/A')}\n\n"
            f"Provide an elaborate comparison that includes:\n"
            f"- Common themes.\n"
            f"- Key differences in themes or approaches.\n"
            f"- Unique ideas or highlights from each talk.\n\n"
            f"Generate a thorough, clear, easy to understand and structured report:"
        )

        # Generate the report using OpenAI
        report = query_openai(prompt)

        # Clean up Markdown syntax from the report
        cleaned_report = re.sub(r'\*\*|__', '', report)  # Remove bold syntax
        cleaned_report = re.sub(r'\n+', '\n', cleaned_report)  # Remove excessive line breaks
        cleaned_report = re.sub(r'- ', '', cleaned_report)  # Remove bullet points if needed

        return {"report": cleaned_report}

    except Exception as e:
        return {"error": f"Error comparing TED Talks: {e}"}



def generate_temp_file(suffix: str) -> str:
    """
    Create a temporary file and return its path.
    """
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.close()
        return temp_file.name
    except Exception as e:
        raise RuntimeError(f"Error creating temporary file: {e}")


def clean_and_validate_mm_content(mm_content: str) -> str:
    """
    Clean and validate the .mm content. Attempt auto-repair if necessary.
    """
    try:
        # Remove Markdown formatting if present
        if mm_content.startswith("```") and mm_content.endswith("```"):
            mm_content = mm_content.split("\n", 1)[1].rsplit("\n", 1)[0].strip()

        print("After removing Markdown formatting:", mm_content)  # Debug log

        # Validate XML
        ET.fromstring(mm_content)
        print("XML validation successful.")  # Debug log
        return mm_content
    except ET.ParseError as e:
        print(f"XML Validation Error: {e}\nAttempting repair...")  # Debug log

        # Attempt auto-repair using lxml
        parser = etree.XMLParser(recover=True)
        tree = etree.parse(StringIO(mm_content), parser)
        repaired_content = etree.tostring(tree, encoding="unicode", pretty_print=True)

        print("Repaired XML content:", repaired_content)  # Debug log
        return repaired_content
    except Exception as e:
        raise ValueError(f"Generated .mm content is invalid XML. Error: {e}")


def generate_mm_content_from_chatgpt(transcript: str) -> str:
    """
    Query ChatGPT to generate valid FreeMind .mm file content and validate the XML structure.
    """
    prompt = (
        "Hi, ChatGPT! From now on you will behave as \"MapGPT\" and, for every text the user will submit, "
        "you are going to create an example of what FreeMind mind map file in the \".mm\" file format for the inputted text might look like. "
        "Format it as a code and remember that the mind map should be in the same language as the inputted text. "
        "You don't have to provide a general example for the mind map format before the user inputs the text. "
        "Example map for an example topic: "
        "<map version=\"1.0.1\">"
        "<node TEXT=\"The Earth\">"
        "<node TEXT=\"Structure\">"
        "<node TEXT=\"Core\" />"
        "<node TEXT=\"Mantle\" />"
        "<node TEXT=\"Crust\" />"
        "</node>"
        "<node TEXT=\"Atmosphere\" />"
        "<node TEXT=\"Hydrosphere\" />"
        "<node TEXT=\"Biosphere\" />"
        "</node>"
        "</map>"
        f"\n\nTranscript:\n{transcript}"
    )

    mm_content = query_openai(prompt).strip()
    print("Raw content from ChatGPT (before cleaning):", mm_content)  # Debug log

    # Clean and validate content
    return clean_and_validate_mm_content(mm_content)


def parse_mm_to_dot(mm_content: str) -> dict:
    """
    Parse .mm content to a Python dictionary using xmltodict.
    """
    try:
        parsed_data = xmltodict.parse(mm_content)
        print("Parsed XML data:", parsed_data)  # Debug log
        return parsed_data
    except Exception as e:
        raise ValueError(f"Failed to parse .mm content as valid XML. Error: {e}")


def generate_colored_dot(data, output_png_path):
    """
    Generate a colored DOT graph from parsed .mm data and save it as a PNG.
    """
    graph = Digraph(format="png", engine="dot")
    graph.attr(rankdir="LR", dpi="150", size="24,12")

    # Root node
    root = data["map"]["node"]
    root_text = root["@TEXT"]
    graph.node(root_text, style="filled", fillcolor="lightblue")

    def add_children(node, parent_text, level):
        if "node" in node:
            children = node["node"] if isinstance(node["node"], list) else [node["node"]]
            for child in children:
                child_text = child["@TEXT"]
                fillcolor = "lightgreen" if level == 1 else "yellow" if level == 2 else "orange"
                graph.node(child_text, style="filled", fillcolor=fillcolor)
                graph.edge(parent_text, child_text)
                add_children(child, child_text, level + 1)

    add_children(root, root_text, level=1)
    graph.render(output_png_path, cleanup=True)
    print(f"Mind map PNG saved at {output_png_path}.png")


def generate_mind_map(transcript: str, output_png_path: str):
    """
    Generate the mind map PNG for the given transcript.
    """
    mm_content = generate_mm_content_from_chatgpt(transcript)
    mm_data = parse_mm_to_dot(mm_content)
    generate_colored_dot(mm_data, output_png_path)








def generate_notes_agent(url: str, notes: str) -> str:
    """
    Generate notes for a TED Talk.
    """
    return f"Playbook for TED Talk '{url}' with user notes: {notes}"

def fetch_transcript_by_slug(slug: str) -> str:
    """
    Fetch the transcript for a TED Talk using its slug.

    Args:
        slug (str): The unique identifier for the TED Talk.

    Returns:
        str: The transcript of the TED Talk.
    """
    try:
        metadata = fetch_metadata_from_s3(S3_BUCKET, slug)
        transcript = metadata.get("transcript", "")
        if not transcript:
            raise ValueError("Transcript not found in metadata.")
        return transcript
    except Exception as e:
        raise RuntimeError(f"Error fetching transcript: {str(e)}")


def extract_themes_from_transcript(transcript: str) -> list:
    """
    Extract themes or buzzwords from a TED Talk transcript using OpenAI's chat models.

    Args:
        transcript (str): Full transcript of the TED Talk.

    Returns:
        list: A list of themes or buzzwords.
    """
    try:
        messages = [
            {"role": "system", "content": "You are an assistant that extracts themes or buzzwords from text."},
            {"role": "user", "content": f"Extract 4 main themes or buzzwords from the following transcript:\n\n{transcript}\n\nProvide the themes as a comma-separated list."}
        ]

        # Query OpenAI chat model
        response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an assistant that extracts themes or buzzwords from text."},
            {"role": "user", "content": f"Extract 4 main themes or buzzwords from the following transcript:\n\n{transcript}\n\nProvide the themes as a comma-separated list."}
        ],
        temperature=0.5,
        max_tokens=100,
    )


        # Parse OpenAI response
        themes_text = response.choices[0].message.content.strip()
        themes = [theme.strip() for theme in themes_text.split(",")]
        return themes
    except Exception as e:
        raise ValueError(f"Error extracting themes: {str(e)}")


def generate_playbook(url: str, notes: str, transcript: str, title: str, speaker: str) -> Dict[str, str]:
    """
    Generate a playbook for a TED Talk using OpenAI.

    Args:
        url (str): URL of the TED Talk.
        notes (str): User-provided notes.
        transcript (str): Transcript of the TED Talk.
        title (str): Title of the TED Talk.
        speaker (str): Speaker of the TED Talk.

    Returns:
        Dict[str, str]: A structured playbook including introduction, main body, conclusion, and synthesized user notes.
    """
    try:
        # Summarize the transcript for the introduction
        summary_prompt = (
            f"The following is the transcript of a TED Talk:\n\n{transcript}\n\n"
            f"Summarize this transcript in a concise paragraph suitable for an introduction."
        )
        introduction = query_openai(summary_prompt)

        # Generate the main body and conclusion
        main_body_prompt = (
            f"Based on the transcript and the talk titled '{title}' by {speaker}, "
            f"write a clear and concise main body that highlights key points and insights from the talk."
        )
        main_body = query_openai(main_body_prompt)

        conclusion_prompt = (
            f"Based on the TED Talk titled '{title}', write a brief and impactful conclusion summarizing "
            f"the main message and takeaway for the audience."
        )
        conclusion = query_openai(conclusion_prompt)

        # Process user notes
        notes_prompt = (
            f"The following are user-provided notes for a TED Talk titled '{title}':\n\n{notes}\n\n"
            f"Synthesize these notes into clear, concise bullet points."
        )
        synthesized_notes = query_openai(notes_prompt) if notes else "No notes provided."

        # Format the final playbook
        playbook_content = (
            f"Title: {title}\n"
            f"Speaker: {speaker}\n"
            f"URL: {url}\n\n"
            f"Introduction:\n{introduction}\n\n"
            f"Main Body:\n{main_body}\n\n"
            f"Conclusion:\n{conclusion}\n\n"
            f"User Notes:\n{synthesized_notes}"
        )

        return {
            "title": title,
            "speaker": speaker,
            "url": url,
            "content": playbook_content,
        }
    except Exception as e:
        raise RuntimeError(f"Error generating playbook: {str(e)}")



def extract_talks_from_message(message: str) -> tuple:
    """
    Extract two TED Talk URLs from a comparison query message.
    
    Args:
        message (str): The user query message containing talk titles or URLs.
    
    Returns:
        tuple: A tuple containing two TED Talk URLs or titles.
    
    Example:
        Input: "Compare How to pitch to a VC and How I started writing songs again"
        Output: ("https://www.ted.com/talks/how_to_pitch_to_a_vc", "https://www.ted.com/talks/how_i_started_writing_songs_again")
    """
    # Extract titles or URLs from the message. Replace with a regex-based approach if needed.
    parts = message.lower().replace("compare", "").split("and")
    if len(parts) == 2:
        talk1 = parts[0].strip()
        talk2 = parts[1].strip()
        return talk1, talk2
    raise ValueError("Unable to extract two TED Talks from the message.")


def parse_qa_message(message: str) -> tuple:
    """
    Parse the QA query to extract the TED Talk URL or title and the user question.

    Args:
        message (str): The user query message for a TED Talk.

    Returns:
        tuple: A tuple containing the TED Talk URL/title and the question.

    Example:
        Input: "What does David Rose talk about in How to pitch to a VC?"
        Output: ("https://www.ted.com/talks/how_to_pitch_to_a_vc", "What does David Rose talk about?")
    """
    # Extract the question and title/URL from the message
    try:
        if "in" in message.lower():
            parts = message.lower().split("in", 1)
            question = parts[0].strip()
            talk_title = parts[1].strip()
            return talk_title, question
        raise ValueError("Message does not contain a valid 'in' separator.")
    except Exception as e:
        raise ValueError(f"Error parsing QA message: {e}")




def generate_playbook_agent(data: dict) -> dict:
    """
    Consolidate a playbook from given data.
    """
    try:
        return {"playbook": f"Consolidated Playbook: {data}"}
    except Exception as e:
        return {"error": str(e)}
