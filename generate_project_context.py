#!/usr/bin/env python3
"""
Project Context Generator
Generates a comprehensive project context file with file tree and code content.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

def should_exclude_file(filepath, script_name, output_file):
    """Check if a file should be excluded from the context."""
    filename = os.path.basename(filepath)
    
    # Exclude the script itself and its output
    if filename == script_name or filename == output_file:
        return True
    
    # Exclude common non-essential files
    excluded_extensions = {'.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.bin', '.log'}
    excluded_dirs = {'__pycache__', '.git', '.vscode', '.idea', 'node_modules', '.pytest_cache'}
    excluded_files = {'.DS_Store', 'Thumbs.db', '.gitignore'}
    
    # Check extension
    _, ext = os.path.splitext(filename)
    if ext.lower() in excluded_extensions:
        return True
    
    # Check if in excluded directory
    for part in Path(filepath).parts:
        if part in excluded_dirs:
            return True
    
    # Check excluded files
    if filename in excluded_files:
        return True
    
    return False

def is_code_file(filepath):
    """Check if a file is a code file that should be included in full."""
    code_extensions = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss', '.sass',
        '.java', '.cpp', '.c', '.h', '.hpp', '.cs', '.php', '.rb', '.go',
        '.rs', '.swift', '.kt', '.scala', '.r', '.sql', '.sh', '.bat',
        '.yaml', '.yml', '.json', '.xml', '.toml', '.ini', '.cfg'
    }
    
    _, ext = os.path.splitext(filepath)
    return ext.lower() in code_extensions

def generate_file_tree(root_path, prefix="", script_name="", output_file=""):
    """Generate a visual file tree representation."""
    tree_lines = []
    
    try:
        items = sorted(os.listdir(root_path))
    except PermissionError:
        return ["Permission denied"]
    
    dirs = [item for item in items if os.path.isdir(os.path.join(root_path, item))]
    files = [item for item in items if os.path.isfile(os.path.join(root_path, item))]
    
    # Filter out excluded items
    dirs = [d for d in dirs if not should_exclude_file(os.path.join(root_path, d), script_name, output_file)]
    files = [f for f in files if not should_exclude_file(os.path.join(root_path, f), script_name, output_file)]
    
    all_items = dirs + files
    
    for i, item in enumerate(all_items):
        is_last = i == len(all_items) - 1
        current_prefix = "└── " if is_last else "├── "
        tree_lines.append(f"{prefix}{current_prefix}{item}")
        
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            extension_prefix = "    " if is_last else "│   "
            subtree = generate_file_tree(item_path, prefix + extension_prefix, script_name, output_file)
            tree_lines.extend(subtree)
    
    return tree_lines

def get_file_content(filepath):
    """Get the content of a file with proper encoding handling."""
    encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
    
    for encoding in encodings:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    return "Unable to read file - encoding not supported"

def collect_code_files(root_path, script_name, output_file):
    """Collect all relevant code files with their relative paths."""
    code_files = []
    
    for root, dirs, files in os.walk(root_path):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if not should_exclude_file(os.path.join(root, d), script_name, output_file)]
        
        for file in files:
            filepath = os.path.join(root, file)
            
            if should_exclude_file(filepath, script_name, output_file):
                continue
                
            if is_code_file(filepath):
                rel_path = os.path.relpath(filepath, root_path)
                code_files.append(rel_path)
    
    return sorted(code_files)

def main():
    script_name = os.path.basename(__file__)
    output_file = "project_context.txt"
    root_path = "."
    
    print(f"Generating project context...")
    print(f"Excluding: {script_name}, {output_file}")
    
    # Generate content
    content_lines = []
    
    # Header
    content_lines.append("=" * 80)
    content_lines.append("PROJECT CONTEXT")
    content_lines.append("=" * 80)
    content_lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    content_lines.append(f"Root directory: {os.path.abspath(root_path)}")
    content_lines.append("")
    
    # File Tree
    content_lines.append("FILE TREE")
    content_lines.append("-" * 40)
    tree_lines = generate_file_tree(root_path, script_name=script_name, output_file=output_file)
    content_lines.extend(tree_lines)
    content_lines.append("")
    
    # Code Files
    content_lines.append("CODE FILES")
    content_lines.append("-" * 40)
    
    code_files = collect_code_files(root_path, script_name, output_file)
    
    if not code_files:
        content_lines.append("No code files found.")
    else:
        for rel_path in code_files:
            filepath = os.path.join(root_path, rel_path)
            content_lines.append("")
            content_lines.append("=" * 60)
            content_lines.append(f"FILE: {rel_path}")
            content_lines.append("=" * 60)
            
            file_content = get_file_content(filepath)
            content_lines.append(file_content)
    
    # Write to output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content_lines))
        
        print(f"✓ Project context generated successfully: {output_file}")
        print(f"✓ Processed {len(code_files)} code files")
        
    except Exception as e:
        print(f"✗ Error writing output file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 