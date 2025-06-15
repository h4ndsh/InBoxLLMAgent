import dotenv
import argparse
import logging
from pathlib import Path
from email_main.email_processor import EmailProcessor
from email_main.email_monitor import EmailMonitor
import threading

def main():
    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Email Processing Script")
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging (DEBUG level)')
    args = parser.parse_args()

    # Set up logging based on the --verbose argument
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('DEBUG.log'),
            logging.StreamHandler()
        ]
    )

    # Log to confirm the logging level
    logging.info(f"Logging level set to: {logging.getLevelName(logging.getLogger().level)}")

    # Path to .env file
    env_path = Path(".env")

    # Check if .env exists before loading
    if env_path.is_file():
        dotenv.load_dotenv(dotenv_path=env_path)
    else:
        logging.ERROR(".env file not found. Exiting")
        exit(1)
    
    # Instantiate EmailProcessor and EmailMonitor
    email_processor = EmailProcessor()
    email_monitor = EmailMonitor()
    
    # Start threads
    email_monitor_thread = threading.Thread(target=email_monitor.start_schedule)
    email_processor_thread = threading.Thread(target=email_processor.start)
    
    try:
        email_processor_thread.start()
        email_monitor_thread.start()
        
        # Wait for threads to finish
        email_processor_thread.join()
        email_monitor_thread.join()
        
    except KeyboardInterrupt:
        logging.debug("Received interrupt signal. Stopping...")
        email_processor.stop()
        email_monitor.stop()
        
        # Wait for threads to finish gracefully
        email_processor_thread.join(timeout=5)
        email_monitor_thread.join(timeout=5)
        
    logging.debug("Application stopped.")

if __name__ == "__main__":
    main()