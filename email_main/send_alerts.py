from email.mime.text import MIMEText
import html
import logging
import smtplib
import os

def generate_phishing_warning(json_data, template_path):
    """Gera o HTML preenchido com base no JSON e no template."""
    # Verificar se o template existe
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
    domains = html.escape(', '.join(json_data['indicators'].get('domains', [])))

    # Processar listas com loops
    urls = json_data['indicators'].get('urls', [])
    urls_html = ''.join(f'<li>{html.escape(url.replace("://", "[:]//"))}</li>' for url in urls)  # Loop para criar itens <li> para URLs
    emails = json_data['indicators'].get('emails', [])
    emails_html = ''.join(f'<li>{html.escape(email)}</li>' for email in emails)  # Loop para criar itens <li> para emails

    # Substituir os placeholders no template
    template = template.replace('$subject', subject)
    template = template.replace('$from', from_email)
    template = template.replace('$to', "diogo.costa@fefal.pt")
    template = template.replace('$date', date)
    template = template.replace('$confidence', confidence)
    template = template.replace('$reasons', reasons)
    template = template.replace('$urls', urls_html if urls else '<li>Nenhum link encontrado</li>')
    template = template.replace('$domains', domains if domains else 'Nenhum domínio encontrado')
    template = template.replace('$emails', emails_html if emails else '<li>Nenhum email encontrado</li>')
    return template, to_email

def send_email(config, subject, html_sender):
    """Envia um email usando SMTP com o corpo em HTML."""
    try:
        body, to_address = html_sender
        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = config['sender_email']['email']
        msg['To'] = to_address
        
        # Conectar ao servidor SMTP
        with smtplib.SMTP(config['sender_email']['server'], config['sender_email']['port']) as server:
            server.starttls()
            server.login(config['sender_email']['username'], config['sender_email']['password'])
            server.sendmail(msg['From'], [msg['To']], msg.as_string())
            logging.debug(f"Email enviado para {to_address}")
    except Exception as e:
        logging.error(f"Erro ao enviar email: {e}")
        raise
