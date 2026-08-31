import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 1. Force load environment variables from .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")


# 2. Define Data Contract (Pega Data Class equivalent)
class FinancialAnalysis(BaseModel):
    category: str = Field(
        description="Category of transaction or summary, e.g., Revenue, Expenses"
    )
    sentiment: str = Field(
        description="Overall sentiment: BULLISH, BEARISH, or NEUTRAL"
    )
    confidence_score: float = Field(description="Confidence score between 0.0 and 1.0")
    key_takeaways: list[str] = Field(description="Key takeaway bullet points")


def main():
    if not api_key:
        raise ValueError("GEMINI_API_KEY was not found in environment or .env file!")

    # Initialize client explicitly with the loaded key
    client = genai.Client(api_key=api_key)
    target_model = "gemini-3.6-flash"

    print(f"--- Step 1: Connectivity Test using {target_model} ---")
    response_text = client.models.generate_content(
        model=target_model,
        contents="Respond with: API verification successful.",
        config=types.GenerateContentConfig(tools=[]),
    )
    print(f"Response: {response_text.text.strip()}\n")

    print("--- Step 2: Enforced JSON Schema Test ---")
    response_schema = client.models.generate_content(
        model=target_model,
        contents="Analyze Q2 performance: Revenue grew 14% YoY, but operating margins compressed due to supply chain costs.",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FinancialAnalysis,
            tools=[],
        ),
    )
    print("Structured JSON Output:")
    print(response_schema.text)


if __name__ == "__main__":
    main()
