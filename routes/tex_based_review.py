import os
import json
from dotenv import load_dotenv
from groq import Groq
import re

def review_chess_game(pgn_file_path):
    # Load environment variables and initialize Groq client
    load_dotenv()
    API_KEY = "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"
    if not API_KEY:
        raise ValueError("API key not found. Please set GROQ_API_KEY in the .env file.")
    client = Groq(api_key=API_KEY)

    # JSON structured prompt
    template = (
    "You are tasked with reviewing a chess game in PGN format: {pgn_content}. "
    "Please provide the analysis in JSON format with the following structure:\n"
    "{{\n"
    '  "summary": "Brief game summary",\n'
    '  "move_reviews": [\n'
    '    {{"move": "e4", "evaluation": "Good", "commentary": "Solid central control"}},\n'
    '    {{"move": "d5", "evaluation": "Brilliant", "commentary": "Aggressive center contest"}}\n'
    '  ],\n'
    '  "biggest_blunders": {{\n'
    '    "player1": "Qxb7",\n'
    '    "player2": "None"\n'
    '  }},\n'
    '  "recommendations": {{\n'
    '    "player1": "Focus on central control",\n'
    '    "player2": "Continue aggressive play"\n'
    '  }}\n'
    "}}\n"
    "Make sure the JSON is well-formatted and does not contain any invalid content."
)

    # Read PGN content
    try:
        with open(pgn_file_path, 'r') as file:
            pgn_content = file.read()
    except FileNotFoundError:
        return {"error": f"File '{pgn_file_path}' not found."}

    # Format the prompt
    prompt = template.format(pgn_content=pgn_content)

    # Interact with Groq API
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=1,
            max_tokens=4096,
            top_p=1,
            stream=True,
            stop=None,
        )

        response_text = ""
        for message in completion:
            if message.choices and message.choices[0].delta.content:
                response_text += message.choices[0].delta.content
        response_text = response_text.strip()

        # Remove unnecessary text before JSON starts
        response_text = re.sub(r"(?s)^.*?\{", "{", response_text).strip()
        response_text = re.sub(r"```json|```", "", response_text).strip()


        # Ensure the response is valid JSON
        try:
            structured_data = json.loads(response_text)
            return structured_data
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse JSON: {str(e)}", "raw_response": response_text}


    except Exception as e:
        return {"error": f"Error processing PGN: {str(e)}"}

def validate_json(review):
    """Check if the input is a valid JSON string or dictionary."""
    if isinstance(review, dict):
        print("Valid JSON (dictionary)")
        return True  # Already a valid Python dictionary
    
    try:
        json.loads(review)  # Attempt to parse JSON string
        print("Valid JSON (string)")
        return True
    except json.JSONDecodeError:
        print("Invalid JSON response")
        return False  # Return False if JSON is invalid

