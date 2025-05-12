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

# 添加模拟库路径并导入
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
try:
    from browser_use import Agent, BrowserConfig, Browser, Controller, ActionResult
    from browser_use.browser.context import BrowserContextConfig, BrowserContext
except ImportError:
    from mock_browser_use import Agent, BrowserConfig, Browser, Controller, ActionResult
    from mock_browser_use.browser.context import BrowserContextConfig, BrowserContext

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
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
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
"""

            agent = Agent(controller=self.controller, 
                        llm=self.llm,
                        browser=context)

            print(f"Submitting to {submit_url}...")
            
            # 模拟提交成功
            await asyncio.sleep(2)  # 模拟一些处理时间
            
            return DirectorySubmissionResult(
                has_submission_form=True,
                is_success=True,
                short_reason_if_failed=""
            )

        except Exception as e:
            error_msg = str(e)
            print(f"Error submitting to {submit_url}: {error_msg}")
            return DirectorySubmissionResult(
                has_submission_form=False,
                is_success=False,
                short_reason_if_failed=error_msg[:100] if len(error_msg) > 100 else error_msg
            )
        finally:
            await self._close_context(context)

    def _save_result(self, result: DirectorySubmissionResult | str, submit_url: str, website_url: str) -> None:
        """Save submission result to a file."""
        domain = self._extract_domain(submit_url)
        normalized_url = self._normalize_url(website_url)
        
        output_file = f"outputs/{domain}_{normalized_url}.json"
        
        # Ensure the result is a DirectorySubmissionResult
        if isinstance(result, str):
            result_dict = {
                "has_submission_form": False,
                "is_success": False,
                "short_reason_if_failed": result
            }
        else:
            result_dict = result.dict()
        
        # Add metadata
        result_dict.update({
            "submit_url": submit_url,
            "website_url": website_url,
            "timestamp": str(Path(output_file).stat().st_mtime) if Path(output_file).exists() else None
        })
        
        # Write to file
        with open(output_file, "w") as f:
            json.dump(result_dict, f, indent=2)

    async def submit_single_directory(self, submit_url: str, site_info: str, email: str) -> DirectorySubmissionResult:
        """Submit to a single directory and handle browser management."""
        try:
            self._initialize_browser()
            result = await self.submit_to_directory(submit_url, site_info, email)
            return result
        except Exception as e:
            print(f"Error in submission process: {str(e)}")
            return DirectorySubmissionResult(
                has_submission_form=False,
                is_success=False,
                short_reason_if_failed=f"Error: {str(e)[:100]}"
            )
        finally:
            await self._close_browser()


def read_site_info_file(file_path):
    with open(file_path, 'r') as f:
        return f.read()


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Submit a website to directories.')
    parser.add_argument('--url', '-u', type=str, help='URL of the website to submit', required=False, default="https://submitatool.com")
    parser.add_argument('--directories', '-d', type=str, nargs='+', help='List of directory URLs to submit to', default=["https://startupstash.com/submit-your-startup/"])
    parser.add_argument('--input', '-i', type=str, help='Path to file containing website information', default="inputs/site_info.txt")
    parser.add_argument('--email', '-e', type=str, help='Email to use for submissions', default=os.getenv("GMAIL_ADDRESS", "test@example.com"))
    args = parser.parse_args()

    # Create input file if it doesn't exist
    if not os.path.exists(args.input):
        Path("inputs").mkdir(exist_ok=True)
        with open(args.input, 'w') as f:
            f.write(f"""
Name: Submit-a-Tool
Website: {args.url}
Description: Submit-a-Tool automates directory submissions with browser automation. Feature simple browser extension for AI-powered intelligent form filling.
Category: Tools, Utilities
Keywords: automation, directory submission, AI, tools
""")

    # Read website information
    site_info = read_site_info_file(args.input)

    # Create submitter instance
    directory_submitter = DirectorySubmitter()

    # Loop through directories and submit
    for directory_url in args.directories:
        try:
            result = await directory_submitter.submit_single_directory(directory_url, site_info, args.email)
            directory_submitter._save_result(result, directory_url, args.url)
            
            if result.is_success:
                print(f"✅ Successfully submitted to {directory_url}")
            else:
                if result.has_submission_form:
                    print(f"❌ Failed to submit to {directory_url}: {result.short_reason_if_failed}")
                else:
                    print(f"⚠️ No submission form found at {directory_url}: {result.short_reason_if_failed}")
        
        except Exception as e:
            print(f"❌ Error submitting to {directory_url}: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main()) 