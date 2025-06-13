import schedule
import time
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from email import message_from_bytes
import imaplib
from datetime import datetime
import threading

class EmailMonitor:
    def __init__(self, config):
        self.config = config
        self.imap_conn = None
        self.max_threads = config.get('max_threads', 5)
        self.interval = config["inbox_email"]["interval"]
        self.executor = ThreadPoolExecutor(max_workers=self.max_threads)
        self.emails_folder = config["inbox_email"]['eml_folder']
        self.running = True
        self.stop_event = threading.Event()
        self.connection_established = False

    def connect_imap(self):
        """Establish IMAP connection to email server"""
        try:
            logging.debug(f"Connecting to {self.config['inbox_email']['server']}:{self.config['inbox_email']['port']} (SSL: {self.config['inbox_email']['ssl']})")
            
            if self.config["inbox_email"]['ssl']:
                self.imap_conn = imaplib.IMAP4_SSL(
                    self.config["inbox_email"]['server'], 
                    self.config["inbox_email"]['port']
                )
            else:
                self.imap_conn = imaplib.IMAP4(
                    self.config["inbox_email"]['server'], 
                    self.config["inbox_email"]['port']
                )
                self.imap_conn.starttls()
            
            self.imap_conn.login(
                self.config["inbox_email"]['username'], 
                self.config["inbox_email"]['password']
            )
            
            self.imap_conn.select('INBOX')
            self.connection_established = True
            logging.debug("IMAP connection established successfully")
            return True
            
        except Exception as e:
            logging.error(f"IMAP connection failed: {e}")
            self.connection_established = False
            return False

    def disconnect_imap(self):
        """Close IMAP connection"""
        try:
            if self.imap_conn:
                try:
                    self.imap_conn.close()
                except:
                    pass  # Ignore close errors
                self.imap_conn.logout()
                self.connection_established = False
                logging.debug("IMAP connection closed")
        except Exception as e:
            logging.error(f"Error closing IMAP connection: {e}")

    def get_unread_emails(self):
        """Retrieve list of unread email IDs"""
        try:
            # Refresh the connection by selecting INBOX again
            self.imap_conn.select('INBOX')
            
            status, messages = self.imap_conn.search(None, 'UNSEEN')
            if status != 'OK' or not messages[0]:
                return []
            
            email_ids = messages[0].decode('utf-8').split()
            return email_ids
            
        except Exception as e:
            logging.error(f"Error fetching unread emails: {e}")
            return []

    def save_email_as_eml(self, raw_email, email_id, email_message):
        """Save email as .eml file"""
        try:
            # Ensure emails folder exists
            if not os.path.exists(self.emails_folder):
                os.makedirs(self.emails_folder)
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            subject = email_message.get('Subject', 'No_Subject')
            
            # Clean subject for filename
            safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
            filename = f"{timestamp}_ID{email_id}_{safe_subject}.eml"
            filepath = os.path.join(self.emails_folder, filename)
            
            with open(filepath, 'wb') as f:
                f.write(raw_email)
                
            logging.debug(f"Email saved as {filename}")
            return filepath
            
        except Exception as e:
            logging.error(f"Error saving email {email_id}: {e}")
            return None

    def process_email(self, email_id):
        """Process individual email"""
        try:
            status, msg_data = self.imap_conn.fetch(email_id, '(RFC822)')
            if status != 'OK':
                logging.error(f"Error fetching email {email_id}")
                return False
                
            raw_email = msg_data[0][1]
            email_message = message_from_bytes(raw_email)

            # Save email as .eml file
            saved_path = self.save_email_as_eml(raw_email, email_id, email_message)
            
            if saved_path:
                # Mark as read only if successfully saved
                self.mark_as_read(email_id)
                return True
            else:
                return False
                
        except Exception as e:
            logging.error(f"Error processing email {email_id}: {e}")
            return False

    def mark_as_read(self, email_id, mark_as_unread=False):
        """Mark email as read or unread"""
        try:
            if mark_as_unread:
                self.imap_conn.store(email_id, '-FLAGS', '\\Seen')  # Remove Seen flag = mark as unread
            else:
                self.imap_conn.store(email_id, '+FLAGS', '\\Seen')  # Add Seen flag = mark as read
        except Exception as e:
            logging.error(f"Error marking email {email_id}: {e}")
    
    def check_emails(self):
        """Check for new emails and process them"""
        try:
            # Check if we should stop
            if self.stop_event.is_set():
                return
                
            # Check if connection is still alive
            if not self.is_connection_alive():
                logging.warning("IMAP connection lost, attempting to reconnect...")
                self.disconnect_imap()
                if not self.connect_imap():
                    logging.error("Failed to reconnect. Will retry on next schedule.")
                    return
            
            unread_emails = self.get_unread_emails()
            
            if unread_emails:
                logging.debug(f"Processing {len(unread_emails)} unread emails.")
                
                # Process each email individually
                for email_id in unread_emails:
                    if self.stop_event.is_set():
                        logging.debug("Stop event received, stopping email processing")
                        break
                        
                    success = self.process_email(email_id)
                    if success:
                        logging.debug(f"Successfully processed email {email_id}")
                    else:
                        logging.error(f"Failed to process email {email_id}")
            else:
                logging.debug("No unread emails found")
                
        except Exception as e:
            logging.error(f"Monitoring error: {e}")
            # Try to reconnect on next iteration
            self.disconnect_imap()
            self.imap_conn = None

    def start_schedule(self):
        """Start the scheduled email monitoring"""
        # Establish initial connection only once
        if not self.connection_established:
            if not self.connect_imap():
                logging.error("Failed to establish initial IMAP connection. Exiting.")
                return
        
        # Schedule the email checking job
        schedule.every(self.interval).seconds.do(self.check_emails)
        
        logging.debug(f"Monitoring scheduled every {self.interval} seconds.")
        
        while self.running and not self.stop_event.is_set():
            schedule.run_pending()
            time.sleep(1)
            
        logging.debug("Email monitoring stopped")

    # Additional helper methods
    def is_connection_alive(self):
        """Check if IMAP connection is still alive"""
        try:
            if not self.imap_conn or not self.connection_established:
                return False
            # Send a NOOP command to check connection
            status, response = self.imap_conn.noop()
            return status == 'OK'
        except:
            return False

    def stop(self):
        """Stop the email monitoring"""
        logging.debug("Stopping email monitor...")
        self.running = False
        self.stop_event.set()
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
        # Close IMAP connection
        self.disconnect_imap()
        
        logging.debug("Email monitor stopped successfully")