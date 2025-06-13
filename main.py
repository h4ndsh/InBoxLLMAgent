import json
import argparse
import logging
import os
from email_main.email_processor import EmailProcessor
from email_main.email_monitor import EmailMonitor
import threading

def load_env_variables(env_file='env.json'):
    #read environment configuration
    if not os.path.exists(env_file):
        logging.error(f"Environment configuration file '{env_file}' not found.")
        raise FileNotFoundError(f"Environment configuration file '{env_file}' not found.")
    with open(env_file, 'r') as f:
        env_config = json.load(f)
    
    # Create emails folder if it doesn't exist
    if not os.path.exists(env_config["inbox_email"]["eml_folder"]):
        os.makedirs(env_config["inbox_email"]["eml_folder"])
    return env_config


def main():
    # Configurar o parser de argumentos
    parser = argparse.ArgumentParser(description="Email Processing Script")
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging (DEBUG level)')
    args = parser.parse_args()

    # Configurar o logging com base no argumento --verbose
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('DEBUG.log'),
            logging.StreamHandler()
        ]
    )

    # Log para confirmar o nível de logging
    logging.info(f"Logging level set to: {logging.getLevelName(logging.getLogger().level)}")

    # Carregar a configuração
    config = load_env_variables()
    if not config:
        logging.error("Não foi possível carregar a configuração")
        return
    
    # Instanciar EmailProcessor e EmailMonitor
    email_processor = EmailProcessor(config)
    email_monitor = EmailMonitor(config)
    
    # Iniciar threads
    email_monitor_thread = threading.Thread(target=email_monitor.start_schedule)
    email_processor_thread = threading.Thread(target=email_processor.start)
    
    try:
        email_processor_thread.start()
        email_monitor_thread.start()
        
        # Aguardar threads terminarem
        email_processor_thread.join()
        email_monitor_thread.join()
        
    except KeyboardInterrupt:
        logging.debug("Received interrupt signal. Stopping...")
        email_processor.stop()
        email_monitor.stop()
        
        # Aguardar threads terminarem graciosamente
        email_processor_thread.join(timeout=5)
        email_monitor_thread.join(timeout=5)
        
    logging.debug("Application stopped.")

if __name__ == "__main__":
    main()
