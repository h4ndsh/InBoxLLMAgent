import json
import logging
import sqlite3

class SQLManager:
    """Classe para gestão da base de dados SQL dos emails processados"""
    
    def __init__(self, db_path="email_analysis.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa a base de dados com as tabelas necessárias"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    subject TEXT,
                    sender TEXT,
                    recipient TEXT,
                    date_received TEXT,
                    footer TEXT,
                    attachments_count INTEGER,
                    emails_found TEXT,
                    urls_found TEXT,
                    domains_found TEXT,
                    size FLOAT,
                    llm_model TEXT,
                    llm_response TEXT,
                    llm_duration REAL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    recheck_status TEXT,
                    recheck_response TEXT,
                    recheck_model TEXT,
                    recheck_at TIMESTAMP
                )
            ''')
            conn.commit()
    
    def save_analysis(self, analysis_data):
        """Guarda a análise de um email na base de dados"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO email_analysis 
                    (filename, subject, sender, recipient, date_received, footer, 
                     attachments_count, emails_found, urls_found, domains_found,
                     size, llm_model, llm_response, llm_duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis_data['filename'],
                    analysis_data['subject'],
                    analysis_data['from'],
                    analysis_data['to'],
                    analysis_data['date'],
                    analysis_data['footer'],
                    len(analysis_data['attachments']),
                    json.dumps(analysis_data['indicators']['emails']),
                    json.dumps(analysis_data['indicators']['urls']),
                    json.dumps(analysis_data['indicators']['domains']),
                    analysis_data['size'],
                    analysis_data['llm']['model'],
                    json.dumps(analysis_data['llm']['response']),
                    analysis_data['llm']['duration']
                ))
                conn.commit()
                logging.debug(f"Análise guardada na BD: {analysis_data['filename']}")
        except Exception as e:
            logging.error(f"Erro ao guardar análise na BD: {e}")
    
    def export_to_sql_file(self, output_file="email_analysis_export.sql"):
        """Exporta os dados para um ficheiro SQL"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                with open(output_file, 'w', encoding='utf-8') as f:
                    for line in conn.iterdump():
                        f.write('%s\n' % line)
            logging.debug(f"Dados exportados para: {output_file}")
        except Exception as e:
            logging.error(f"Erro ao exportar SQL: {e}")
    
    def get_pending_recheck(self):
        """Obtém registos pendentes de recheck"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM email_analysis 
                WHERE recheck_status = 'pending'
            ''')
            return cursor.fetchall()
    
    def update_recheck(self, filename, recheck_response, recheck_model):
        """Atualiza o resultado do recheck"""
        # TODO: Implementar recheck com outro modelo LLM
        # Este é o local onde deve ser implementado o recheck com outro modelo
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE email_analysis 
                SET recheck_status = 'completed',
                    recheck_response = ?,
                    recheck_model = ?,
                    recheck_at = CURRENT_TIMESTAMP
                WHERE filename = ?
            ''', (json.dumps(recheck_response), recheck_model, filename))
            conn.commit()