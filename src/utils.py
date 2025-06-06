import re
import os
from urllib.parse import unquote

def fix_turkish_characters(text: str) -> str:
    """
    Fixes text that was incorrectly decoded as latin1/iso-8859-1 instead of utf-8.
    This is a common "mojibake" issue where multi-byte UTF-8 characters are
    interpreted as single-byte characters.
    """
    try:
        # This re-encodes the wrongly-decoded string back to its original bytes,
        # then correctly decodes it as UTF-8.
        return text.encode('latin1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        # If it fails, the string was likely already correct or has a different issue.
        return text

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename or directory name by removing illegal characters,
    stripping leading/trailing whitespace, and truncating to a max length.
    Properly handles Turkish characters by first fixing them.
    """
    if not filename:
        return "_unknown_"
    
    # First, fix potential character encoding issues.
    filename = fix_turkish_characters(filename)
    
    # Whitelist approach: Keep Unicode letters, numbers, underscore, whitespace, period, hyphen, parentheses.
    # Replace anything else with a single underscore.
    filename = re.sub(r'[^\w\s.()İıŞşĞğÇçÜüÖö-]', '_', filename, flags=re.UNICODE)
    
    # Replace multiple underscores with a single one.
    filename = re.sub(r'_+', '_', filename)
    
    # Strip leading/trailing whitespace AND underscores. 
    filename = filename.strip(' _')

    if not filename:
        return "_sanitized_empty_"

    # Truncate filename if it's too long, preserving extension.
    MAX_COMPONENT_LENGTH = 100
    if len(filename) > MAX_COMPONENT_LENGTH:
        name, ext = os.path.splitext(filename)
        
        if not ext and name == filename:
            filename = filename[:MAX_COMPONENT_LENGTH]
        else:
            ext_len = len(ext)
            name = name[:MAX_COMPONENT_LENGTH - ext_len]
            filename = name + ext
            
            if len(filename) > MAX_COMPONENT_LENGTH or (not name and ext):
                filename = filename[:MAX_COMPONENT_LENGTH]
                if not filename:
                    return "_truncated_empty_"

    if filename.endswith('.'):
        filename = filename[:-1] + '_'

    reserved_names = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    if filename.upper() in reserved_names:
        filename += "_"
    
    if not filename:
        return "_final_empty_fallback_"
        
    return filename

def extract_filename(content_disposition: str) -> str:
    """
    A robust attempt to parse RFC 5987 (filename*=UTF-8\'\') or old-school filename=\"...\".
    The result of this function should be passed to sanitize_filename.
    """
    if not content_disposition:
        return None

    # 1) Check for filename*= (RFC 5987)
    match_filename_star = re.search(r'filename\*\s*=\s*(?:[^\\\']+\\\'\\\')?(.+)', content_disposition, flags=re.IGNORECASE)
    if match_filename_star:
        encoded_part = match_filename_star.group(1).strip()
        if encoded_part.startswith("UTF-8''"):
            encoded_part = encoded_part[len("UTF-8''"):]
        try:
            decoded = unquote(encoded_part, encoding='utf-8', errors='replace')
            # Ensure proper handling of Turkish characters
            decoded = decoded.encode('latin1').decode('utf-8')
            return decoded
        except UnicodeError:
            return unquote(encoded_part, encoding='utf-8', errors='replace')

    # 2) Otherwise fallback to filename=
    match_filename = re.search(r'filename\s*=\s*("([^"]+)"|([^";]+))', content_disposition, flags=re.IGNORECASE)
    if match_filename:
        filename_candidate = match_filename.group(1)
        filename_candidate = filename_candidate.strip('"')
        try:
            filename_candidate = unquote(filename_candidate, encoding='utf-8', errors='replace')
            # Ensure proper handling of Turkish characters
            filename_candidate = filename_candidate.encode('latin1').decode('utf-8')
            return filename_candidate
        except UnicodeError:
            return unquote(filename_candidate, encoding='utf-8', errors='replace')

    return None 