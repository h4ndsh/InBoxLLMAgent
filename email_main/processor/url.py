import requests
import logging

def google_safe_browsing(url, api_key=None):
    # Check for API key
    if api_key is None:
        error_msg = "Google Safe Browsing API key not provided."
        logging.error(error_msg)
        raise ValueError(error_msg)

    # Normalize input: accept string or list of URLs
    urls = [url] if isinstance(url, str) else url
    if not urls:
        return {"matches": [], "error": None}

    # Set up API URL
    api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"

    # Create payload for the API
    payload = {
        "client": {
            "clientId": "phishing_detector",
            "clientVersion": "1.0"
        },
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",  # Phishing
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION"
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": u} for u in urls]
        }
    }

    try:
        # Make the API call
        response = requests.post(api_url, json=payload)
        response.raise_for_status()  # Raise exception for HTTP errors
        result = response.json()

        # Return results
        matches = result.get("matches", [])
        return {"matches": matches, "error": None}

    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP error when calling Safe Browsing API: {e}"
        logging.error(error_msg)
        return {"matches": [], "error": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error when calling Safe Browsing API: {e}"
        logging.error(error_msg)
        return {"matches": [], "error": error_msg}
    except ValueError as e:
        error_msg = f"Error processing API response: {e}"
        logging.error(error_msg)
        return {"matches": [], "error": error_msg}