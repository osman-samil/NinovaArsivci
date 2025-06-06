import re
import os

# Helper function to sanitize file and folder names
def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename or directory name by removing illegal characters,
    stripping leading/trailing whitespace, and truncating to a max length.
    Properly handles Turkish characters.
    """
    if not filename:
        return "_unknown_"
    
    # First ensure proper encoding of Turkish characters
    try:
        filename = filename.encode('latin1').decode('utf-8')
    except UnicodeError:
        pass  # If encoding fails, use the original string
    
    # Whitelist approach: Keep Unicode letters, numbers, underscore, whitespace, period, hyphen, parentheses, and specific Turkish chars.
    # Replace anything else with a single underscore.
    # \w includes underscore. \s includes space. Explicitly list . ( ) - and Turkish chars. Hyphen at the end.
    filename = re.sub(r'[^\w\s.()İıŞşĞğÇçÜüÖö-]', '_', filename, flags=re.UNICODE)
    
    # Replace multiple underscores (possibly from previous step or original name) with a single one.
    filename = re.sub(r'_+', '_', filename)
    
    # Strip leading/trailing whitespace AND underscores. 
    filename = filename.strip(' _')

    # If filename becomes empty after stripping (e.g., was all spaces/underscores or illegal chars)
    if not filename:
        return "_sanitized_empty_"

    # Truncate filename if it's too long, preserving extension.
    MAX_COMPONENT_LENGTH = 100
    if len(filename) > MAX_COMPONENT_LENGTH:
        name, ext = os.path.splitext(filename)
        
        # Handle cases like ".bashrc" where the name starts with a dot and has no other dot.
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

    # Final check for names that are problematic on Windows
    if filename.endswith('.'):
        filename = filename[:-1] + '_'

    # Check for reserved names (case-insensitive on Windows)
    reserved_names = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    if filename.upper() in reserved_names:
        filename += "_"
    
    if not filename:
        return "_final_empty_fallback_"
        
    return filename 