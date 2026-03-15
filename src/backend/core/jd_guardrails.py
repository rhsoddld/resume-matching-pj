import re
import logging

logger = logging.getLogger(__name__)

# Basic heuristic for prompt injection in JDs
_PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+previous\s+instructions\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous\s+)?instructions\b",
    r"\bsystem\s+prompt\b",
    r"\byou\s+are\s+(?:now\s+)?an?\s+(?:ai|assistant)\b",
    r"\bforget\s+(?:all\s+)?(?:previous\s+)?instructions\b",
    r"\bbypass\s+(?:all\s+)?filters\b",
]

_INJECTION_RE = re.compile("|".join(_PROMPT_INJECTION_PATTERNS), re.IGNORECASE)

def optimize_jd_tokens(jd_text: str, max_chars: int = 8000) -> str:
    """
    Cleans up excessive whitespace and truncates the JD to a max character limit
    to prevent token limits and reduce costs.
    """
    if not jd_text:
        return ""
    
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", jd_text).strip()
    
    # Truncate
    if len(cleaned) > max_chars:
        logger.warning(f"JD exceeded {max_chars} chars. Truncating to {max_chars}.")
        cleaned = cleaned[:max_chars]
        
    return cleaned

def scan_for_prompt_injection(jd_text: str) -> bool:
    """
    Scans the JD for obvious prompt injection attempts.
    Returns True if an injection attempt is detected.
    """
    if not jd_text:
        return False
        
    if _INJECTION_RE.search(jd_text):
        logger.warning("Prompt injection detected in JD.")
        return True
        
    return False

def wrap_untrusted_jd(jd_text: str) -> str:
    """
    Wraps the JD in XML tags to help the LLM distinguish user content from instructions.
    """
    if not jd_text:
        return ""
    # Prevent the user from injecting closing tags
    safe_text = jd_text.replace("</job_description>", "")
    return f"<job_description>\n{safe_text}\n</job_description>"
