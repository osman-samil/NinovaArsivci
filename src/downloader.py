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
from src.announcement_handler import archive_announcements_for_course
from src.homework_handler import archive_homeworks_for_course
from src.utils import sanitize_filename, extract_filename

import re
import os
import uuid
import requests
import time

MIN_FILE_SIZE_TO_LAUNCH_NEW_THREAD = 5  # MB, reverted from 0.01

SINIF_DOSYALARI_URL_EXTENSION = "/SinifDosyalari"
DERS_DOSYALARI_URL_EXTENSION = "/DersDosyalari"

thread_list: list[Thread] = []


def download_all_in_course(course: Course) -> None:
    global URL

    # Create a unique folder name using the course code and CRN.
    # This prevents conflicts between different sections of the same course.
    unique_folder_name = f"{course.code} (CRN {course.crn})"
    sanitized_folder_name = sanitize_filename(unique_folder_name)
    subdir_name = join(globals.BASE_PATH, sanitized_folder_name)

    session = globals.session_copy()

    # Ensure base course directory exists
    os.makedirs(subdir_name, exist_ok=True)

    # --- Sınıf Dosyaları ---
    raw_html_sinif = session.get(
        URL + course.link + SINIF_DOSYALARI_URL_EXTENSION
    ).content.decode("utf-8")
    klasor_sinif_name = sanitize_filename("Sınıf Dosyaları")
    klasor_sinif_path = join(subdir_name, klasor_sinif_name)
    os.makedirs(klasor_sinif_path, exist_ok=True)
    _download_or_traverse(raw_html_sinif, klasor_sinif_path)

    # --- Ders Dosyaları ---
    raw_html_ders = session.get(
        URL + course.link + DERS_DOSYALARI_URL_EXTENSION
    ).content.decode("utf-8")
    klasor_ders_name = sanitize_filename("Ders Dosyaları")
    klasor_ders_path = join(subdir_name, klasor_ders_name)
    os.makedirs(klasor_ders_path, exist_ok=True)
    _download_or_traverse(raw_html_ders, klasor_ders_path)

    # --- Duyurular (Delegated to the new handler) ---
    archive_announcements_for_course(course, session)

    # --- Ödevler (Delegated to the new handler) ---
    archive_homeworks_for_course(course, session, _download_file)

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
                    ),
                )
                large_file_thread.start()
                thread_list.append(large_file_thread)
            else:
                _download_file(
                    URL + file_link, destionation_folder
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


def _download_file(file_url: str, destination_folder: str):
    session = globals.session_copy()
    
    # --- Pre-download DB check ---
    if not globals.FIRST_RUN:
        file_id = extract_file_id(file_url)
        if file_id != -1:
            cursor = DB.get_new_cursor() 
            status = DB.check_file_status(file_id, cursor)
            cursor.close()
            if status == FILE_STATUS.EXISTS:
                logger.verbose(f"File with ID {file_id} already in DB. Skipping download.")
                return

    # --- NEW: Retry mechanism for network errors ---
    file_binary = None
    downloaded_filename = None
    MAX_RETRIES = 3
    RETRY_DELAY = 5 # seconds

    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(file_url, stream=True, allow_redirects=True, timeout=(10, 60))
            resp.raise_for_status()
            
            content_disposition = resp.headers.get('content-disposition', '')
            if content_disposition:
                try:
                    content_disposition = content_disposition.encode('latin1').decode('utf-8')
                except UnicodeError:
                    pass
            
            downloaded_filename = extract_filename(content_disposition)

            if downloaded_filename:
                downloaded_filename = sanitize_filename(downloaded_filename)
            else:
                downloaded_filename = sanitize_filename("unknown_" + str(uuid.uuid4())[:8] + ".bin")
            
            file_binary = resp.content
            break # Success, exit the retry loop

        except requests.exceptions.RequestException as e:
            logger.warning(f"Download failed for {file_url} on attempt {attempt + 1}/{MAX_RETRIES}. Retrying in {RETRY_DELAY}s... Error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"All download attempts failed for {file_url}. Skipping file.")
                return # Give up after all retries

    if not downloaded_filename or file_binary is None:
        logger.warning(f"Filename or binary content could not be determined for {file_url} after retries.")
        return

    try:
        file_full_name = join(destination_folder, downloaded_filename)
        file_full_name = file_full_name.encode('utf-8').decode('utf-8')
    except UnicodeError:
        logger.error(f"Failed to encode file path: {file_full_name}")
        return

    if exists(file_full_name):
        with open(file_full_name, "rb") as ex_file:
            existing_hash = crc32(ex_file.read())
        
        new_hash = crc32(file_binary)

        if new_hash != existing_hash:
            extension_dot_index = downloaded_filename.rfind(".")
            base_name_for_new = downloaded_filename
            ext_for_new = ""
            if extension_dot_index != -1:
                base_name_for_new = downloaded_filename[:extension_dot_index]
                ext_for_new = downloaded_filename[extension_dot_index:]
            
            new_filename_candidate = base_name_for_new + "_yeni" + ext_for_new
            counter = 1
            file_full_name = join(destination_folder, new_filename_candidate)
            while exists(file_full_name):
                counter += 1
                new_filename_candidate = f"{base_name_for_new}_yeni_{counter}{ext_for_new}"
                file_full_name = join(destination_folder, new_filename_candidate)
            downloaded_filename = new_filename_candidate
        else:
            logger.verbose(
                f"File {file_full_name} already exists with the same content. Skipping."
            )
            return
    
    try:
        with open(file_full_name, "wb") as bin_file:
            bin_file.write(file_binary)
        logger.verbose(f"Successfully downloaded and saved: {file_full_name}")
    except IOError as e:
        logger.error(f"Failed to write file {file_full_name}: {e}")
        return

    DB.add_file(extract_file_id(file_url), file_full_name)


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