import dkim
import re

def dkim_passes_from_bytes(eml_bytes, enable=False):
    debug_msgs = []
    if not enable:
        return debug_msgs
    # Look for raw DKIM-Signature header
    dkim_signature = None
    for line in eml_bytes.split(b"\n"):
        if line.lower().startswith(b"dkim-signature:"):
            dkim_signature = line.decode(errors="ignore").strip()
            break

    if not dkim_signature:
        debug_msgs.append("DKIM-Signature header NOT found.")
        return debug_msgs

    debug_msgs.append("DKIM-Signature found.")

    # Extract selector (s=) and domain (d=) from signature
    selector = None
    domain = None
    match_selector = re.search(r"s=([^;]+)", dkim_signature)
    match_domain = re.search(r"d=([^;]+)", dkim_signature)
    if match_selector:
        selector = match_selector.group(1)
        debug_msgs.append(f"DKIM Selector: {selector}")
    else:
        debug_msgs.append("DKIM Selector NOT found")

    if match_domain:
        domain = match_domain.group(1)
        debug_msgs.append(f"DKIM Domain: {domain}")
    else:
        debug_msgs.append("DKIM Domain NOT found")

    # Verify DKIM and return result
    try:
        valid = dkim.verify(eml_bytes)
        result = "PASS" if valid else "FAIL"
    except Exception as e:
        result = f"ERROR ({e})"

    debug_msgs.append(f"DKIM Result: {result}")

    return debug_msgs
