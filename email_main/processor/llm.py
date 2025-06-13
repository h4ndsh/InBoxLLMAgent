import logging
import requests
import time
import re
import json

def build_prompt(content, indicators, language="EN"):
    return (
        "You are an AI specialized in phishing detection. Your task is to analyze the email in a step-by-step manner to decide if it is 'phishing' or 'legitimate'.\n\n"
        "Follow this order when analyzing:\n"
        "1. Examine the 'From' field: check if the sender's email/domain is trusted or suspicious.\n"
        "2. Analyze the extracted domains: check if they are known legitimate domains or suspicious/fake ones.\n"
        "3. Review the email body: look for phishing signs such as urgency, suspicious links, requests for credentials, spelling mistakes, or spoofing.\n"
        "4. Use Google Safe Browsing results to check if any URLs are flagged as malicious.\n"
        "5. Use other extracted indicators (emails, links, DKIM results) to complement your judgment.\n\n"
        "Assign relative weights to each part (From, Domains, Body, Safe Browsing, Other Indicators) to build your confidence score.\n"
        "If evidence is weak or mixed, lower the confidence.\n\n"
        "Your response MUST be ONLY a valid JSON object in this exact format:\n\n"
        "{\n"
        '  "verdict": "phishing" or "legitimate",\n'
        '  "confidence": "low", "medium" or "high",\n'
        f'  "reasons": ["Provide exactly three short, clear reasons in {language}"]\n'
        "}\n\n"
        "STRICT RULES:\n"
        "- DO NOT output anything except the JSON object.\n"
        "- DO NOT use markdown, explanations, or extra text.\n"
        "- ALWAYS use the exact JSON structure.\n"
        "- Base your decision strictly on the data below.\n"
        "- Use realistic confidence values reflecting the evidence strength.\n\n"
        "== EMAIL METADATA ==\n"
        f"From: {content['from']}\n\n"
        "== EXTRACTED DOMAINS ==\n"
        f"{', '.join(indicators['domains']) or 'None'}\n\n"
        "== EMAIL BODY ==\n"
        f"{content['body']}\n\n"
        "== GOOGLE SAFE BROWSING RESULTS ==\n"
        f"{''.join(f'{url}: ' + ', '.join([d['threatType'] for d in matches]) + '\\n' if matches else f'{url}: None\\n' for url, matches in indicators.get('google_safe_browsing', {}).items()) or 'None\\n'}\n"
        "== OTHER EXTRACTED INDICATORS ==\n"
        f"Emails: {', '.join(indicators['emails']) or 'None'}\n"
        f"DKIM Info:\n{indicators.get('dkim', 'None')}\n"
    )



def extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None

def check_phishing(content, indicators, ollama_api_url, model, auth_token, stream, language):
    prompt = build_prompt(content, indicators, language)
    
    headers = {
        "Content-Type": "application/json"
    }
    
    if auth_token is not None:
        # add authentication token if provided
        headers["Authorization"] = f"Bearer {auth_token}"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": stream
    }
    # get size of the payload in kb
    payload_size_kb = len(json.dumps(payload).encode('utf-8')) / 1024
    
    try:
        start_time = time.time()
        logging.debug("Waiting for LLM response...")
        response = requests.post(ollama_api_url, headers=headers, json=payload)
        response.raise_for_status()
        end_time = time.time()

        raw_result = response.json().get("response", "")
        parsed = extract_json(raw_result)

        return parsed if parsed else raw_result, end_time - start_time, payload_size_kb

    except Exception as e:
        return f"Error contacting Ollama API: {e}", None
