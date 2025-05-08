from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.kampus import Course

from os import mkdir, rmdir, stat, unlink, walk
from os.path import abspath, dirname, exists, getsize, join, normpath, splitdrive
from src import logger
from bs4 import BeautifulSoup, element
from threading import Thread
from zlib import crc32

from src import globals
from src.login import URL
from src.db_handler import DB, FILE_STATUS

import re
from urllib.parse import unquote
import os
import uuid
import requests

MIN_FILE_SIZE_TO_LAUNCH_NEW_THREAD = 5  # MB, reverted from 0.01

SINIF_DOSYALARI_URL_EXTENSION = "/SinifDosyalari"
DERS_DOSYALARI_URL_EXTENSION = "/DersDosyalari"

thread_list: list[Thread] = []


def download_all_in_course(course: Course) -> None:
    global URL

    # Sanitize the course code for the main directory name
    sanitized_course_code = sanitize_filename(course.code)
    subdir_name = join(globals.BASE_PATH, sanitized_course_code)

    session = globals.session_copy()

    # Ensure base course directory exists
    os.makedirs(subdir_name, exist_ok=True)


    raw_html_sinif = session.get(
        URL + course.link + SINIF_DOSYALARI_URL_EXTENSION
    ).content.decode("utf-8")

    # Sanitize "Sınıf Dosyaları" folder name
    klasor_sinif_name = sanitize_filename("Sınıf Dosyaları")
    klasor_sinif_path = join(subdir_name, klasor_sinif_name)
    os.makedirs(klasor_sinif_path, exist_ok=True)

    _download_or_traverse(raw_html_sinif, klasor_sinif_path)

    raw_html_ders = session.get(
        URL + course.link + DERS_DOSYALARI_URL_EXTENSION
    ).content.decode("utf-8")

    # Sanitize "Ders Dosyaları" folder name
    klasor_ders_name = sanitize_filename("Ders Dosyaları")
    klasor_ders_path = join(subdir_name, klasor_ders_name)
    os.makedirs(klasor_ders_path, exist_ok=True)

    _download_or_traverse(raw_html_ders, klasor_ders_path)

    for thread in thread_list:
        thread.join()


def _get_mb_file_size_from_string(raw_file_size: str) -> float:
    size_info = raw_file_size.strip().split(" ")
    size_as_float = float(size_info[0])
    if size_info[1] == "KB":
        size_as_float /= 1024
    return size_as_float


def _download_or_traverse(raw_html: str, destionation_folder: str) -> None:
    session = globals.session_copy()
    try:
        rows = BeautifulSoup(raw_html, "lxml")
        rows = rows.select_one(".dosyaSistemi table.data").find_all("tr")
    except:
        return  # 'dosya' başka bir sayfaya link ise
    rows.pop(0)  # ilk satır tablonun başlığı

    row: element.Tag
    for row in rows:
        info = _parse_file_info(row)
        if info:
            file_link, file_size, isFolder, file_name = info
            if isFolder:
                _traverse_folder(
                    URL + file_link, destionation_folder, file_name
                )
            elif file_size > MIN_FILE_SIZE_TO_LAUNCH_NEW_THREAD:  # mb
                large_file_thread = Thread(
                    target=_download_file,
                    args=(
                        URL + file_link,
                        destionation_folder,
                        DB.get_new_cursor(),
                    ),
                )
                large_file_thread.start()
                thread_list.append(large_file_thread)
            else:
                _download_file(
                    URL + file_link, destionation_folder, DB.get_new_cursor()
                )


def _parse_file_info(row: element.Tag):
    try:
        file_info = row.find_all("td")  # ("td").find("a")
        file_a_tag = file_info[0].find("a")
        file_name = sanitize_filename(file_a_tag.text)
        file_size = _get_mb_file_size_from_string(file_info[1].text)
        isFolder = file_info[0].find("img")["src"].endswith("/folder.png")
        file_link = file_a_tag["href"]
    except:
        return None

    return file_link, file_size, isFolder, file_name


def _traverse_folder(folder_url, current_folder, new_folder_name):
    session = globals.session_copy()
    resp = session.get(folder_url)
    sanitized_new_folder_name = sanitize_filename(new_folder_name)
    subdir_name = join(current_folder, sanitized_new_folder_name)
    try:
        os.makedirs(subdir_name, exist_ok=True)
    except FileExistsError:
        pass

    folder_thread = Thread(
        target=_download_or_traverse,
        args=(resp.content.decode("utf-8"), subdir_name),
    )
    folder_thread.start()
    thread_list.append(folder_thread)


def _download_file(file_url: str, destination_folder: str, cursor):
    session = globals.session_copy()
    
    file_binary = None
    downloaded_filename = None

    try:
        resp = session.get(file_url, stream=True, allow_redirects=True, timeout=(10, 60)) # Added timeout
        resp.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        content_disposition = resp.headers.get('content-disposition', '')
        downloaded_filename = extract_filename(content_disposition)

        # Sanitize the filename obtained from header or generated fallback
        if downloaded_filename:
            downloaded_filename = sanitize_filename(downloaded_filename)
        else:
            downloaded_filename = sanitize_filename("unknown_" + str(uuid.uuid4())[:8] + ".bin")
        
        file_binary = resp.content # Get content after successful header processing

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading {file_url}: {e}")
        return # Stop processing this file if initial download fails

    if not downloaded_filename: # Should be handled by sanitize_filename providing a fallback
        logger.warning(f"Filename could not be determined for {file_url} after sanitization.")
        return

    file_full_name = join(destination_folder, downloaded_filename)

    # Dosya zaten mevcutsa ve hash eşleşmiyorsa yeni bir ad ver
    if exists(file_full_name):
        with open(file_full_name, "rb") as ex_file:
            existing_hash = crc32(ex_file.read())
        
        # We already have file_binary and downloaded_filename from the first download attempt
        new_hash = crc32(file_binary)

        if new_hash != existing_hash:
            extension_dot_index = downloaded_filename.rfind(".") # Use sanitized name
            base_name_for_new = downloaded_filename
            ext_for_new = ""
            if extension_dot_index != -1:
                base_name_for_new = downloaded_filename[:extension_dot_index]
                ext_for_new = downloaded_filename[extension_dot_index:]
            
            new_filename_candidate = base_name_for_new + "_yeni" + ext_for_new
            counter = 1
            file_full_name = join(destination_folder, new_filename_candidate)
            # Ensure the new name is also unique if "_yeni" already exists
            while exists(file_full_name):
                counter += 1
                new_filename_candidate = f"{base_name_for_new}_yeni_{counter}{ext_for_new}"
                file_full_name = join(destination_folder, new_filename_candidate)
            downloaded_filename = new_filename_candidate # Update filename to be saved
        else:
            if not globals.FIRST_RUN: # Potential manual intervention or already downloaded
                logger.verbose(
                    f"File {file_full_name} already exists with the same content. Skipping."
                )
            return # File is identical, no need to save or log to DB again if already there
    # else: # File does not exist, file_binary is from the initial download above.
        # No need for _download_from_server here if the first resp.content was successful.

    # Dosyayı yazma
    try:
        with open(file_full_name, "wb") as bin_file:
            bin_file.write(file_binary)
        logger.verbose(f"Successfully downloaded and saved: {file_full_name}")
    except IOError as e:
        logger.error(f"Failed to write file {file_full_name}: {e}")
        return

    # Veritabanına ekleme
    DB.add_file(extract_file_id(file_url), file_full_name)


def extract_filename(content_disposition: str) -> str:
    """
    A robust attempt to parse RFC 5987 (filename*=UTF-8\'\') or old-school filename=\"...\".
    The result of this function should be passed to sanitize_filename.
    Removed decode_weird_turkish call.
    """
    if not content_disposition:
        return None

    # 1) Check for filename*= (RFC 5987)
    match_filename_star = re.search(r'filename\*\s*=\s*(?:[^\\\']+\\\'\\\')?(.+)', content_disposition, flags=re.IGNORECASE)
    if match_filename_star:
        encoded_part = match_filename_star.group(1).strip()
        if encoded_part.startswith("UTF-8''"):
            encoded_part = encoded_part[len("UTF-8''"):]
        decoded = unquote(encoded_part, encoding='utf-8', errors='replace')
        return decoded

    # 2) Otherwise fallback to filename=
    match_filename = re.search(r'filename\s*=\s*("([^"]+)"|([^";]+))', content_disposition, flags=re.IGNORECASE)
    if match_filename:
        filename_candidate = match_filename.group(1)
        filename_candidate = filename_candidate.strip('"')
        filename_candidate = unquote(filename_candidate, errors='replace')
        return filename_candidate

    return None


def extract_file_id(file_url: str) -> int:
    """
    Dosya URL'sinden file_id'yi çıkarır.
    """
    match = re.search(r'\?g(\d+)', file_url)
    if not match:
        logger.warning(f"Geçersiz dosya URL formatı (eksik '?g<numara>'): {file_url}")
        return -1
    
    file_id_str = match.group(1)
    try:
        file_id = int(file_id_str)
        return file_id
    except ValueError:
        logger.warning(f"Çıkarılan file_id bir tam sayı değil: '{file_id_str}' from URL: {file_url}")
        return -1


@logger.speed_measure("indirme işlemi", False, True)
def _download_from_server(session, file_url: str): # This function is now primarily for cases where only content is needed
                                                 # And _download_file handles its own primary download.
                                                 # Consider if this is still needed or if _download_file's logic is enough.
                                                 # For now, _download_file was refactored to not call this for the main binary.
    try:
        resp = session.get(file_url, timeout=(10,60)) # Added timeout
        resp.raise_for_status()
        content_disposition = resp.headers.get("content-disposition", "")
        filename = extract_filename(content_disposition)
        # Note: filename from here is not sanitized by this function directly.
        # The caller should sanitize if using it for path construction.
        if not filename:
            filename = "bilinmeyen_dosya_from_download_from_server" # To differentiate if used
        return filename, resp.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Secondary download attempt via _download_from_server for {file_url} failed: {e}")
        return "error_filename", b"" # Return empty bytes and error indicator


# Helper function to sanitize file and folder names
def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename or directory name by removing illegal characters,
    stripping leading/trailing whitespace, and truncating to a max length.
    """
    if not filename:
        return "_unknown_"
    
    # Whitelist approach: Keep Unicode letters, numbers, underscore, whitespace, period, hyphen, parentheses, and specific Turkish chars.
    # Replace anything else with a single underscore.
    # \w includes underscore. \s includes space. Explicitly list . ( ) - and Turkish chars. Hyphen at the end.
    filename = re.sub(r'[^\w\s.()İıŞşĞğÇçÜüÖö-]', '_', filename, flags=re.UNICODE)
    
    # Replace multiple underscores (possibly from previous step or original name) with a single one.
    filename = re.sub(r'_+', '_', filename)
    
    # Strip leading/trailing whitespace AND underscores. 
    # If a name becomes just "_", this will make it empty.
    filename = filename.strip(' _')

    # If filename becomes empty after stripping (e.g., was all spaces/underscores or illegal chars)
    if not filename:
        return "_sanitized_empty_"

    # Truncate filename if it's too long, preserving extension.
    MAX_COMPONENT_LENGTH = 100  # Max length for a single path component
    if len(filename) > MAX_COMPONENT_LENGTH:
        name, ext = os.path.splitext(filename)
        
        # Handle cases like ".bashrc" where the name starts with a dot and has no other dot.
        # In this case, os.path.splitext(".bashrc") returns (".bashrc", "")
        # and os.path.splitext("longfilename") returns ("longfilename", "")
        if not ext and name == filename: # No extension, or name is like ".bashrc"
            filename = filename[:MAX_COMPONENT_LENGTH]
        else: # Has an extension
            ext_len = len(ext)
            # Reserve space for extension, truncate name part.
            name = name[:MAX_COMPONENT_LENGTH - ext_len]
            filename = name + ext
            
            # If the reconstructed filename is still too long (e.g., extension itself was too long)
            # or if name became empty (e.g. MAX_COMPONENT_LENGTH was smaller than ext_len)
            # then fall back to a hard truncation of the whole string.
            if len(filename) > MAX_COMPONENT_LENGTH or (not name and ext):
                 filename = filename[:MAX_COMPONENT_LENGTH]
                 # ensure it's not empty after hard truncate
                 if not filename: return "_truncated_empty_"


    # Final check for names that are problematic on Windows like CON, PRN, AUX, NUL, COM1-9, LPT1-9
    # Also, names cannot end with a period or a space on Windows.
    # The .strip() above handles trailing spaces. Let's check for trailing periods.
    if filename.endswith('.'):
        filename = filename[:-1] + '_' # Replace trailing period with underscore

    # Check for reserved names (case-insensitive on Windows)
    reserved_names = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    if filename.upper() in reserved_names:
        filename += "_" # Append underscore if it's a reserved name
    
    if not filename: # If it somehow became empty after all this (e.g. was just ".")
        return "_final_empty_fallback_"
        
    return filename