from email.mime.text import MIMEText
import html
import logging
import smtplib
import os

def generate_phishing_warning(json_data, template_name):
    """Gera o HTML preenchido com base no JSON e no template."""
    print(template_name)
    # Verificar se o template existe em static/
    template_path = os.path.join(os.path.dirname(__file__), 'static', template_name)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template HTML não encontrado em: {template_path}")

    # Ler o template HTML
    with open(template_path, 'r', encoding='utf-8') as file:
        template = file.read()

    # Extrair os dados do JSON
    subject = html.escape(json_data.get('subject', 'Desconhecido'))
    from_email = html.escape(json_data.get('from', 'Desconhecido'))
    to_email = html.escape(json_data.get('to').split('<')[-1].strip('>'))
    date = html.escape(json_data.get('date', 'Desconhecida'))
    confidence = json_data['llm']['response'].get('confidence', 0)
    reasons = html.escape(' '.join(json_data['llm']['response'].get('reasons', ['Nenhuma razão fornecida.'])))
    
    # Processar listas com loops
    emails = json_data['indicators'].get('emails', [])
    emails_html = ''.join(f'<li>{html.escape(email)}</li>' for email in emails)
    domains = json_data['indicators'].get('domains', [])
    domains_html = ''.join(f'<li>{html.escape(domain)}</li>' for domain in domains)

    # Substituir os placeholders no template
    template = template.replace('$subject', subject)
    template = template.replace('$from', from_email)
    template = template.replace('$date', date)
    template = template.replace('$confidence', confidence)
    template = template.replace('$reasons', reasons)
    template = template.replace('$domains', domains_html if domains else None)
    template = template.replace('$emails', emails_html if emails else None)
    return template, to_email

def send_email(subject, html_sender):
    """Envia um email usando SMTP com o corpo em HTML."""
    try:
        body, to_address = html_sender
        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = os.getenv("SENDER_EMAIL")
        msg['To'] = to_address
        
        # Conectar ao servidor SMTP
        with smtplib.SMTP(os.getenv("SENDER_SERVER"), os.getenv("SENDER_PORT")) as server:
            server.starttls()
            server.login(os.getenv("SENDER_USERNAME"), os.getenv("SENDER_PASSWORD"))
            server.sendmail(msg['From'], [msg['To']], msg.as_string())
            logging.debug(f"Email enviado para {to_address}")
    except Exception as e:
        logging.error(f"Erro ao enviar email: {e}")
        raise
