"""Utility functions for resume screening with LLMs."""

from typing import Any, Dict
import httpx
import json
import csv


def load_resumes(csv_path: str) -> Dict[str, Dict[str, str]]:
    """
    Load all resumes from CSV into a dictionary.

    Args:
        csv_path: Path to the resumes CSV file

    Returns:
        Dict mapping resume ID to resume data (ID, Resume_str, Resume_html)
    """
    resumes = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            resumes[row['ID']] = {
                'ID': row['ID'],
                'Resume_str': row['Resume_str'],
                'Resume_html': row['Resume_html']
            }
    return resumes


def load_job_requirements(file_path: str) -> str:
    """
    Load job requirements from a markdown file.

    Args:
        file_path: Path to the job requirements markdown file

    Returns:
        String contents of the job requirements file
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def analyze_resume(
    api_key: str,
    prompt: str,
    resume_text: str,
    output_schema: str,
    model: str = "anthropic/claude-sonnet-4.6",
    temperature: float = 0.3
) -> Dict[str, Any]:
    """
    Analyze a resume using an LLM with structured output.

    Args:
        api_key: OpenRouter API key
        prompt: The instruction for what to analyze
        resume_text: The resume text to analyze
        output_schema: JSON schema description for the output format
        model: Model to use (default: Claude 3.5 Sonnet)
        temperature: Sampling temperature (default: 0.3 for consistency)

    Returns:
        Dict with 'result' (parsed JSON), 'error' (if any), and 'usage' (token counts)
    """
    # Build the full prompt
    full_prompt = f"""{prompt}

Resume:
{resume_text[:3000]}

Return a JSON object with this structure:
{output_schema}

Return ONLY valid JSON, no additional text."""

    # Make API call
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": temperature,
        "max_tokens": 1500,
        "response_format": {"type": "json_object"}
    }

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                return {
                    "result": None,
                    "error": f"API error: {data['error']}",
                    "usage": {},
                }

            content = data["choices"][0]["message"]["content"]
            if not content:
                return {
                    "result": None,
                    "error": f"Empty response from model. Raw response: {data}",
                    "usage": data.get("usage", {}),
                }

            # Strip markdown code fences if present
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]  # remove ```json line
                cleaned = cleaned.rsplit("```", 1)[0]  # remove trailing ```
                cleaned = cleaned.strip()

            result = json.loads(cleaned)

            return {
                "result": result,
                "error": None,
                "usage": data.get("usage", {})
            }
    except json.JSONDecodeError as e:
        return {
            "result": None,
            "error": f"Failed to parse JSON: {e}. Raw content: {content!r}",
            "usage": data.get("usage", {}),
        }
    except Exception as e:
        return {
            "result": None,
            "error": str(e),
            "usage": {}
        }


def submit_score(
    team_name: str,
    resume_id: str,
    score: float,
    api_url: str = "http://ai-leaderboard.site",
    api_key: str = "lecture2-secret-key",
) -> dict:
    """
    Submit a resume score to the leaderboard.

    Args:
        team_name: Your team's name
        resume_id: The resume ID being scored
        score: Score from 0-100
        api_url: Leaderboard server URL
        api_key: API key for authentication

    Returns:
        Dict with server response
    """
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            f"{api_url}/api/submit",
            json={"team_name": team_name, "resume_id": str(resume_id), "score": score},
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()
