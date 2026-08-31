import os
from dotenv import load_dotenv
from google import genai

# Force load environment variables from root /app/.env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")


def main():
    if not api_key:
        raise ValueError("GEMINI_API_KEY was not found in environment or .env file!")

    client = genai.Client(api_key=api_key)

    print("--- Step 1: Managed Agent Execution ---")

    # Managed Agents run inside a sandboxed Linux harness via client.interactions
    interaction = client.interactions.create(
        agent="antigravity-preview-05-2026",
        input=(
            "Write a simple Python script to calculate the sum of prime numbers "
            "under 100, execute it in the shell environment, and report the output."
        ),
    )

    print("Agent Response:")
    print(interaction.output_text)


if __name__ == "__main__":
    main()
