import re
import os

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