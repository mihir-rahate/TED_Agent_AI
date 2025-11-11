import pytest
from agent import (
    extract_slug_from_url,
    chatbot_agent,
    fetch_metadata_from_s3,
    get_related_talks_agent,
    query_openai
)

# Test slug extraction from valid URL
def test_extract_slug_from_url_valid():
    url = "https://www.ted.com/talks/sting_how_i_started_writing_songs_again"
    slug = extract_slug_from_url(url)
    assert slug == "sting_how_i_started_writing_songs_again"

# Test slug extraction from invalid URL
def test_extract_slug_from_url_invalid():
    with pytest.raises(ValueError, match="Invalid TED Talk URL"):
        extract_slug_from_url("https://example.com/invalid-url")

# Test metadata fetching
def test_fetch_metadata_from_s3(mocker):
    mock_s3_client = mocker.patch("agent.s3_client.get_object", return_value={
        "Body": b'{"title": "Sample Talk", "transcript": "Sample Transcript"}'
    })

    metadata = fetch_metadata_from_s3("bucket_name", "sample_slug")
    assert metadata["title"] == "Sample Talk"
    assert metadata["transcript"] == "Sample Transcript"

# Test chatbot agent for valid metadata
def test_chatbot_agent_valid(mocker):
    mocker.patch("agent.fetch_metadata_from_s3", return_value={
        "title": "Sample Talk",
        "transcript": "This is a sample transcript."
    })
    mocker.patch("agent.query_openai", return_value="Sample Answer")

    response = chatbot_agent("https://www.ted.com/talks/sample_slug", "What is this talk about?")
    assert response == "Sample Answer"

# Test chatbot agent for invalid URL
def test_chatbot_agent_invalid_url():
    response = chatbot_agent("https://example.com/invalid-url", "What is this talk about?")
    assert "Invalid TED Talk URL" in response

# Test related talks fetching
def test_get_related_talks_agent(mocker):
    mocker.patch("agent.fetch_metadata_from_s3", return_value={
        "title": "Sample Talk"
    })
    mocker.patch("agent.search_talks_agent", return_value={
        "results": [
            {"slug": "talk1", "title": "Talk 1"},
            {"slug": "talk2", "title": "Talk 2"}
        ]
    })

    related_talks = get_related_talks_agent("sample_slug")
    assert len(related_talks) == 2

# Test OpenAI query
def test_query_openai(mocker):
    mock_openai_client = mocker.patch("agent.client.chat.completions.create", return_value={
        "choices": [{"message": {"content": "Mocked OpenAI Response"}}]
    })

    response = query_openai("Test prompt")
    assert response == "Mocked OpenAI Response"
