import os
import json
import urllib.parse
import asyncio
import argparse
import imaplib
import email
from email.header import decode_header
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

# 导入browser_use库
from browser_use import Agent, BrowserConfig, Browser, Controller, ActionResult
from browser_use.browser.context import BrowserContextConfig, BrowserContext

from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()


class DirectorySubmissionResult(BaseModel):
    has_submission_form: bool
    is_success: bool
    short_reason_if_failed: str

def read_gmail(_: str) -> str:
    """
    Read unread emails from Gmail via IMAP and return their content.

    Args:
        email_address: The email address to check for unread messages

    Returns:
        ActionResult with the combined content of unread emails
    """
    try:
        # Connect to Gmail IMAP server
        mail = imaplib.IMAP4_SSL("imap.gmail.com")

        # Login with credentials from environment variables
        gmail_address = os.getenv("GMAIL_ADDRESS")
        password = os.getenv("GMAIL_PASSWORD")
        if not password:
            return ActionResult(extracted_content="Error: GMAIL_PASSWORD environment variable not set")

        mail.login(gmail_address, password)

        # Select the inbox
        mail.select("INBOX")

        # Search for unread messages
        status, message_ids = mail.search(None, "UNSEEN")

        if status != "OK" or not message_ids[0]:
            return ActionResult(extracted_content="No unread emails found")

        # Process all unread emails
        content_parts = []
        for message_id in message_ids[0].split():
            # Fetch the email
            status, msg_data = mail.fetch(message_id, "(RFC822)")

            if status != "OK":
                continue

            # Parse the raw email
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Get email subject
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else "utf-8")

            # Get sender
            from_header, encoding = decode_header(msg.get("From", ""))[0]
            if isinstance(from_header, bytes):
                from_header = from_header.decode(encoding if encoding else "utf-8")

            # Extract email content
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain" or content_type == "text/html":
                        try:
                            body = part.get_payload(decode=True).decode()
                            content_parts.append(f"Subject: {subject}\nFrom: {from_header}\n\n{body}")
                            break
                        except:
                            pass
            else:
                # For non-multipart emails
                body = msg.get_payload(decode=True).decode()
                content_parts.append(f"Subject: {subject}\nFrom: {from_header}\n\n{body}")

        # Combine all emails
        combined_content = "\n\n--- Next Email ---\n\n".join(content_parts)
        if not combined_content:
            combined_content = "No readable content found in unread emails"

        # Close connection
        mail.close()
        mail.logout()

        return ActionResult(extracted_content=combined_content)
    except Exception as e:
        return ActionResult(extracted_content=f"Error reading emails: {str(e)}")

async def upload_file(index: int, path: str, browser: BrowserContext, available_file_paths: list[str]):
	if not any(path.startswith(p) for p in available_file_paths):
		return ActionResult(error=f'File path {path} is not available. Available file paths: {available_file_paths}')

	if not os.path.exists(path):
		return ActionResult(error=f'File {path} does not exist')

	dom_el = await browser.get_dom_element_by_index(index)

	file_upload_dom_el = dom_el.get_file_upload_element()

	if file_upload_dom_el is None:
		msg = f'No file upload element found at index {index}'
		print(msg)
		return ActionResult(error=msg)

	file_upload_el = await browser.get_locate_element(file_upload_dom_el)

	if file_upload_el is None:
		msg = f'No file upload element found at index {index}'
		print(msg)
		return ActionResult(error=msg)

	try:
		await file_upload_el.set_input_files(path)
		msg = f'Successfully uploaded file to index {index}'
		print(msg)
		return ActionResult(extracted_content=msg, include_in_memory=True)
	except Exception as e:
		msg = f'Failed to upload file to index {index}: {str(e)}'
		print(msg)
		return ActionResult(error=msg)


def ask_human(question: str) -> str:
    input('\n等待人工介入\n')
    return ActionResult(extracted_content="finished")


class DirectorySubmitter:

    def __init__(self):
        self.browser_config = BrowserConfig()

        self.controller = Controller(output_model=DirectorySubmissionResult, exclude_actions=["search_google"])
        self.controller.action('Read emails, useful for email verification')(read_gmail)
        self.controller.action('Upload file to interactive element with file path')(upload_file)
        self.controller.action('Ask human for difficult CAPTCHA verification')(ask_human)

        self.LLM_MODEL = "claude-3-7-sonnet-20250219"
        self.claude_llm = ChatAnthropic(model=self.LLM_MODEL, base_url=os.getenv("CLAUDE_BASE_URL"), api_key=os.getenv("CLAUDE_API_KEY"))
        self.openai_llm = ChatOpenAI(model="gpt-4o", base_url=os.getenv("OPENAI_BASE_URL"), api_key=os.getenv("OPENAI_API_KEY"))
        self.llm = self.openai_llm if os.getenv("OPENAI_API_KEY") else self.claude_llm

        Path("outputs").mkdir(exist_ok=True)
        Path("accounts").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        Path("logs/conversation").mkdir(exist_ok=True)

        self.browser = None

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for filename purposes."""
        parsed_url = urllib.parse.urlparse(url)
        normalized = parsed_url.netloc + parsed_url.path
        normalized = normalized.replace('/', '_').replace(':', '_').replace('.', '_')
        return normalized

    def _get_context_for_domain(self, domain: str) -> BrowserContext:
        """Get browser context with cookies specific to the domain."""
        cookies_file = f"accounts/cookies_{domain}.json"

        context_config = BrowserContextConfig(
            cookies_file=cookies_file,
            wait_for_network_idle_page_load_time=3.0,
            browser_window_size={'width': 1280, 'height': 2000},
            locale='en-US',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
            # highlight_elements=True,
            # viewport_expansion=-1,
        )

        return BrowserContext(browser=self.browser, config=context_config)

    def _initialize_browser(self):
        """Initialize a new browser instance."""
        self.browser = Browser(config=self.browser_config)

    async def _close_browser(self):
        """Close the current browser instance."""
        if hasattr(self, 'browser'):
            await self.browser.close()

    async def _close_context(self, context):
        """Close a browser context."""
        if context:
            await context.close()

    async def _close_all_tabs(self, context):
        """Close all tabs in the browser context."""
        if context:
            try:
                # Get all pages (tabs) in the context
                pages = await context._context.pages()
                # Close each page
                for page in pages:
                    await page.close()
                print("All tabs closed successfully")
            except Exception as e:
                print(f"Error closing tabs: {str(e)}")

    async def submit_to_directory(self, submit_url: str, site_info: str, email: str) -> DirectorySubmissionResult:
        """Submit website information to a directory listing."""
        domain = self._extract_domain(submit_url)
        context = self._get_context_for_domain(domain)

        try:
            task_description = f"""
Go to {submit_url}
Goal: submit my product to the website.

Use the following information to fill out the submission form:
{site_info}

Use {email} for any email fields required.

Return if only paid options are available.

If login is required before submitting, try to login with the email {email} and password {os.getenv("SUBMIT_ACCOUNT_PASSWORD")}
if login fails, register with the email and password.

If verification is needed, use the `read_gmail` tool to check the email for verification links.

Always Remember: Don't open the Terms of Service or privacy policy, just agree. DO NOT CLICK OR OPEN Terms of Service or Privacy Policy; if you see the tab is ToS or Privacy Policy, close the tab.

Wait and review after clicking the submit button, see if it's successful or more actions are needed.
Your ultimate goal is to successfully submit the website information to the directory.

If you see a CAPTCHA that you cannot solve, use the `ask_human` tool to solve it.
"""

            agent = Agent(
                browser_context=context,
                task=task_description,
                # llm=self.claude_llm,
                llm=self.openai_llm,
                controller=self.controller,
                save_conversation_path="logs/conversation",
                # use_vision=False, # DeepSeek does not support vision
                use_vision=True,
                available_file_paths=["inputs/", os.path.abspath("inputs/")],
            )

            history = await agent.run(max_steps=30)
            result = history.final_result()

            # Explicitly close all tabs
            await self._close_all_tabs(context)

            return result
        finally:
            # Make sure context is closed
            await self._close_context(context)

    def _save_result(self, result: DirectorySubmissionResult | str, submit_url: str, website_url: str) -> None:
        """Save result to the appropriate output files."""
        domain = self._extract_domain(website_url)

        parsed_model = None
        if isinstance(result, str):
            try:
                parsed_model = DirectorySubmissionResult.model_validate_json(result)
                result = parsed_model
            except Exception as e:
                print(f"Failed to parse result as DirectorySubmissionResult: {str(e)[:100]}")
                # Just save the raw string as JSON for failed parsing
                with open(f"outputs/{domain}_fail.json", "a") as f:
                    f.write(f"{json.dumps({'raw_result': result})}\n")
                return

        # Save to results.json
        with open("outputs/results.json", "a") as f:
            if result:
                f.write(f"{result.model_dump_json()}\n")

    async def submit_single_directory(self, submit_url: str, site_info: str, email: str) -> DirectorySubmissionResult:
        """Submit to a single directory.

        This method handles initializing and closing the browser.
        """
        # Initialize a new browser for this URL
        self._initialize_browser()

        try:
            result = await self.submit_to_directory(submit_url, site_info, email)
            website_url = None
            for line in site_info.splitlines():
                if line.startswith("Website:"):
                    website_url = line.replace("Website:", "").strip()
                    break

            if not website_url:
                website_url = "unknown_website"

            self._save_result(result, submit_url, website_url)
            return result
        except Exception as e:
            print(f"Error processing submission at {submit_url}: {str(e)}")
            # Create a failure result
            result = DirectorySubmissionResult(
                has_submission_form=False,
                is_success=False,
                short_reason_if_failed=f"Error: {str(e)[:100]}"
            )

            # Extract website URL from site_info for logging purposes
            website_url = None
            for line in site_info.splitlines():
                if line.startswith("Website:"):
                    website_url = line.replace("Website:", "").strip()
                    break

            if not website_url:
                website_url = "unknown_website"

            self._save_result(result, submit_url, website_url)
            return result
        finally:
            # Close the browser after processing
            await self._close_browser()

def read_site_info_file(file_path):
    """Read the entire site information file as a string."""
    with open(file_path, 'r') as f:
        return f.read()


async def main():
    parser = argparse.ArgumentParser(description='Submit website information to directories')
    parser.add_argument('input_file', help='Path to input file containing directory submission URLs (one per line). You can find the url lists on https://submitatool.com/')
    parser.add_argument('--site_info', '-s', required=True, help='Path to file containing website information')

    args = parser.parse_args()

    try:
        # Read the site information file
        site_info = read_site_info_file(args.site_info)

        # Get email from environment variables
        email = os.getenv("GMAIL_ADDRESS")
        if not email:
            print("Error: GMAIL_ADDRESS environment variable not set")
            return

        directory_submitter = DirectorySubmitter()

        # Read URLs from input file
        with open(args.input_file, "r") as f:
            lines = f.readlines()

        # Process each URL
        for line in lines:
            submit_url = line.strip()
            if not submit_url or submit_url.startswith("#"):
                continue

            # Extract website for logging purposes
            website_url = None
            for info_line in site_info.splitlines():
                if info_line.startswith("Website:"):
                    website_url = info_line.replace("Website:", "").strip()
                    break

            if not website_url:
                website_url = "unknown_website"

            print(f"Processing: {submit_url} with website {website_url}")
            await directory_submitter.submit_single_directory(
                submit_url,
                site_info,
                email
            )
    except Exception as e:
        print(f"Error in main process: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())


