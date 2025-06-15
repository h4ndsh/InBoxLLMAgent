import json
import time
import os
import logging
from email import policy
from email.parser import BytesParser
import re
import email_main.processor.llm as LLM
import email_main.send_alerts as EmailSender
from email_main.sqlmanager import SQLManager
import email_main.processor.url as URLProcessor
import email_main.processor.dkim as DKIMProcessor
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import threading

class EmailProcessor:
    def __init__(self):
        self.emails_folder = os.getenv("INBOX_EML_FOLDER")
        self.processed_folder = os.getenv("INBOX_PROCESSED_FOLDER")
        self.sql_manager = SQLManager()
        self.interval = int(os.getenv("WAIT_INTERVAL_LLM"))
        self.running = True
        self.stop_event = threading.Event()
        self._processing = False 
        
        # Create processed folder if it does not exist
        os.makedirs(self.processed_folder, exist_ok=True)

    def extract_indicators(self, text):
        """Extract emails, URLs and domains from text"""
        emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        url_pattern = re.compile(r"""(?i)\bhttps?://[^\s"'<>()]+""", re.IGNORECASE)
        raw_urls = url_pattern.findall(text)
        clean_urls = [url.rstrip('">).,;') for url in raw_urls]
        domains = list({urlparse(url).netloc for url in clean_urls if urlparse(url).netloc})
        return {
            "emails": list(set(emails)),
            "urls": list(set(clean_urls)),
            "google_safe_browsing": {},
            "domains": domains
        }

    def extract_email_components(self, raw_email):
        """Extract header, body (only visible text), footer, and attachments from the email"""
        try:
            email_message = BytesParser(policy=policy.default).parsebytes(raw_email)
            headers = dict(email_message.items())
            body = ""
            footer = ""
            attachments = []
            plain_body_found = False
            html_body = ""

            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    disposition = part.get('Content-Disposition')
                    payload = part.get_payload(decode=True)
                    if content_type == 'text/plain' and not disposition and payload:
                        body = payload.decode('utf-8', errors='ignore')
                        plain_body_found = True
                    elif content_type == 'text/html' and not disposition and payload:
                        html_body = payload.decode('utf-8', errors='ignore')
                    elif disposition and 'attachment' in disposition.lower():
                        filename = part.get_filename()
                        if filename:
                            attachments.append({
                                'filename': filename,
                                'content': payload
                            })
            else:
                payload = email_message.get_payload(decode=True)
                body = payload.decode('utf-8', errors='ignore') if payload else ""

            if not plain_body_found and html_body:
                soup = BeautifulSoup(html_body, 'html.parser')
                body = soup.get_text()

            footer_lines = [line for line in body.split('\n') if 'unsubscribe' in line.lower() or 'sent from' in line.lower()]
            footer = '\n'.join(footer_lines) if footer_lines else ""
            
            return {
                'headers': headers,
                'body': body.strip(),
                'footer': footer.strip(),
                'attachments': attachments
            }
        except Exception as e:
            logging.error(f"Error extracting email components: {e}")
            return None

    def process_single_email(self, filename):
        """Process a single email file"""
        filepath = os.path.join(self.emails_folder, filename)
        processed_filepath = os.path.join(self.processed_folder, filename)
        
        # Skip if already in processed folder
        if os.path.exists(processed_filepath):
            logging.debug(f"Skipping {filename}: already in processed folder")
            return None
        
        try:
            logging.debug(f"Analyzing: {filename}")
            if not os.path.exists(filepath):
                logging.warning(f"File {filepath} does not exist")
                return None
            
            with open(filepath, 'rb') as f:
                raw_email = f.read()

            # Move file immediately after reading to prevent reprocessing
            try:
                os.rename(filepath, processed_filepath)
                logging.debug(f"File moved to: {processed_filepath}")
            except Exception as e:
                logging.error(f"Error moving file {filename}: {e}")
                return None

            email_message = BytesParser(policy=policy.default).parsebytes(raw_email)
            components = self.extract_email_components(raw_email)
            dkim_ok = DKIMProcessor.dkim_passes_from_bytes(raw_email, os.getenv("DKIM_ENABLED"))
            
            if not components:
                logging.warning(f"Could not extract components from {filename}")
                return None

            indicators = self.extract_indicators(components['body'])
            indicators['dkim'] = dkim_ok
            
            if os.getenv("GOOGLE_SAFE_BROWSING_ENABLED"):
                for url in indicators['urls']:
                    try:
                        result = URLProcessor.google_safe_browsing(
                            url=url,
                            api_key=os.getenv("GOOGLE_SAFE_BROWSING_API_KEY")
                        )
                        if result["matches"]:
                            indicators['google_safe_browsing'][url] = result["matches"]
                    except Exception as e:
                        logging.error(f"Error checking URL {url} with Google Safe Browsing: {e}")
                        
            body_without_urls = re.sub(r'https?://[^\s]+', '', components['body'])

            result, duration, size = LLM.check_phishing(
                content={
                    'from': email_message['From'],
                    'subject': email_message['Subject'],
                    'body': body_without_urls
                },
                indicators=indicators,
                ollama_api_url=os.getenv("OLLAMA_URL"),
                model=os.getenv("OLLAMA_MODEL"),
                auth_token=os.getenv("OLLAMA_AUTH_TOKEN"),
                stream=os.getenv("OLLAMA_STREAM", "false").lower() == "true",
                language=os.getenv("OLLAMA_RESPONSE_LANGUAGE")
            )

            analysis_data = {
                'filename': filename,
                'subject': email_message['Subject'],
                'from': email_message['From'],
                'to': email_message['To'],
                'date': email_message['Date'],
                'footer': components['footer'],
                'attachments': components['attachments'],
                'indicators': indicators,
                'size': size,
                'llm': {
                    'model': os.getenv("OLLAMA_MODEL"),
                    'response': result,
                    'duration': duration
                }
            }
            
            print(f"\n{'='*50}")
            print(f"ANALYSIS COMPLETE: {filename}")
            print(f"{'='*50}")
            print(json.dumps(analysis_data['llm'], indent=4, ensure_ascii=False))
            print(f"{'='*50}\n")

            self.sql_manager.save_analysis(analysis_data)

            if os.getenv("SEND_EMAIL_ALERTS"):
                if analysis_data['llm']['response'].get('verdict') == 'phishing':
                    try:
                        EmailSender.send_email(
                            subject=f"Phishing Alert: {analysis_data['subject']}",
                            html_sender=EmailSender.generate_phishing_warning(
                                json_data=analysis_data,
                                template_name=os.path.join(os.getenv("ALERT_TEMPLATE"))
                            )
                        )
                    except Exception as e:
                        logging.error(f"Error sending alert for {filename}: {e}")

            return analysis_data

        except Exception as e:
            logging.error(f"Error processing {filename}: {e}")
            return None

    def get_oldest_email(self):
        """Get the oldest .eml file in the emails_folder based on modification time"""
        try:
            if not os.path.exists(self.emails_folder):
                logging.error(f"Folder {self.emails_folder} does not exist.")
                return None
            
            eml_files = [f for f in os.listdir(self.emails_folder) if f.endswith('.eml')]
            if not eml_files:
                logging.debug("No emails found to process")
                return None
            
            # Get the oldest file based on modification time
            oldest_file = min(
                eml_files,
                key=lambda f: os.path.getmtime(os.path.join(self.emails_folder, f))
            )
            return oldest_file
        except Exception as e:
            logging.error(f"Error getting oldest email: {e}")
            return None

    def process_emails(self):
        """Process all emails in the folder sequentially, return when no emails remain"""
        if self._processing:
            logging.debug("Already processing an email, skipping")
            return None
        
        self._processing = True
        processed_count = 0
        results = []
        try:
            while self.running and not self.stop_event.is_set():
                filename = self.get_oldest_email()
                if not filename:
                    logging.debug("No more emails to process")
                    break
                
                logging.debug(f"Processing oldest email: {filename}")
                result = self.process_single_email(filename)
                
                if result:
                    processed_count += 1
                    results.append(result)
                    logging.debug(f"Successfully processed: {filename}")
                else:
                    logging.error(f"Failed to process: {filename}")
                
                # Small pause to avoid overloading
                time.sleep(0.5)
            
            if processed_count > 0:
                try:
                    self.sql_manager.export_to_sql_file()
                    logging.debug(f"Processed {processed_count} emails and exported to SQL.")
                except Exception as e:
                    logging.error(f"Error exporting to SQL: {e}")
            
            return results if results else None
        except Exception as e:
            logging.error(f"Error in process_emails: {e}")
            return None
        finally:
            self._processing = False

    def start(self):
        """Start processing emails sequentially, wait when folder is empty"""        
        try:
            while self.running and not self.stop_event.is_set():
                # Process all emails in the folder
                result = self.process_emails()
                if not result:  # No emails were processed (folder is empty)
                    logging.debug(f"Waiting {self.interval} seconds for new emails...")
                    time.sleep(self.interval)
                # Continue immediately if emails were processed
        except KeyboardInterrupt:
            logging.debug("Keyboard interrupt received")
        finally:
            self.stop()
            
        logging.debug("Email processor stopped.")

    def stop(self):
        """Stop the email processing"""
        logging.debug("Stopping email processor...")
        self.running = False
        self.stop_event.set()
        try:
            if hasattr(self.sql_manager, 'close'):
                self.sql_manager.close()
        except Exception as e:
            logging.error(f"Error closing SQL manager: {e}")
        logging.debug("Email processor stopped successfully")

    def get_processing_stats(self):
        """Get processing statistics"""
        try:
            if not os.path.exists(self.emails_folder):
                return {"pending": 0, "processed": 0}
                
            eml_files = [f for f in os.listdir(self.emails_folder) if f.endswith('.eml')]
            processed_files = []
            
            if os.path.exists(self.processed_folder):
                processed_files = [f for f in os.listdir(self.processed_folder) if f.endswith('.eml')]
            
            return {
                "pending": len(eml_files),
                "processed": len(processed_files)
            }
        except Exception as e:
            logging.error(f"Error getting processing stats: {e}")
            return {"pending": 0, "processed": 0}