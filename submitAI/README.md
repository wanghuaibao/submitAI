# Submit-a-Tool: Automated Website Submission with Browser-use

This project provides a simple script (`submit_a_tool.py`) to automate the process of submitting information to directory websites, leveraging the power of `browser-use` for browser automation.  It demonstrates how to extend `browser-use` with custom actions, such as handling file uploads.  While the project currently focuses on simple navigation and submission, it provides a foundation for more complex automation tasks.

## Features

*   Automated navigation and form filling on directory websites.
*   Custom `browser-use` action for handling file uploads (e.g., screenshots).
*   Example of extending `browser-use` capabilities.
*   Basic framework for adding more complex interactions (e.g., email verification – currently includes Gmail related code which may not be fully utilized for the main propose).

## Requirements

*   Python >= 3.11
*   Playwright (for browser automation)
*   OpenAI API Key (for LLM integration)
*   Claude API Key (for LLM integration)

## Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/oldcai/submit-a-tool
    cd submit-a-tool
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

3.  **Set environment variables:**

    Create a `.env` file in the project root directory and add your API keys and a password:

    ```
    OPENAI_API_KEY=your_openai_api_key
    CLAUDE_API_KEY=your_claude_api_key
    SUBMIT_ACCOUNT_PASSWORD=your_password
    ```
    *   Replace `your_openai_api_key`, `your_claude_api_key`, and `your_password` with your actual credentials. The `SUBMIT_ACCOUNT_PASSWORD` is likely used within the script for any login processes.

## Usage

The main script is `submit_a_tool.py`.  It's designed to submit information to a pre-selected directory website.  You can modify the script to target different websites or customize the submission data.

**A list of directory websites that have been tested and are known to work (at the time of writing) can be found at: https://submitatool.com/**

To run the script:

```bash
python submit_a_tool.py
