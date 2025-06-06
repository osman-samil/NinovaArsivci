from __future__ import annotations
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.kampus import Course
    import requests

import os
import re
from os.path import join, exists
from bs4 import BeautifulSoup

from src import logger, globals
from src.login import URL
from src.utils import sanitize_filename, fix_turkish_characters, extract_filename

HOMEWORK_URL_EXTENSION = "/Odevler"

def _dump_html_for_debug(course_crn: str, response: requests.Response, page_name: str):
    """Saves the raw HTML of a page to the central debug_output folder for inspection."""
    debug_filename = f"DEBUG_{page_name}_CRN_{course_crn}.html"
    debug_filepath = join(globals.DEBUG_PATH, debug_filename)
    try:
        # Use response's apparent encoding to save the debug file accurately
        encoding = response.encoding if response.encoding else 'iso-8859-9'
        with open(debug_filepath, "w", encoding=encoding) as f:
            f.write(response.text)
        logger.debug(f"Raw HTML for {page_name} saved for inspection: {debug_filepath}")
    except Exception as e:
        logger.error(f"Debug HTML dosyası kaydedilirken hata oluştu: {e}")


def _handle_postback_download(page_soup: BeautifulSoup, session: requests.Session, href_value: str, destination_folder: str):
    """Handles the download of files linked via ASP.NET's __doPostBack mechanism."""
    try:
        form = page_soup.find("form", id="aspnetForm")
        if not form:
            logger.warning("Postback formu bulunamadı, dosya indirilemiyor.")
            return

        match = re.search(r"__doPostBack\('([^']*)'", href_value)
        if not match:
            logger.warning(f"Postback event target ayrıştırılamadı: {href_value}")
            return
        event_target = match.group(1)

        post_data = {field.get("name"): field.get("value") for field in form.find_all("input")}
        post_data['__EVENTTARGET'] = event_target
        
        post_url = URL + form['action']
        logger.verbose(f"Postback isteği gönderiliyor: {post_url} (Event: {event_target})")

        file_response = session.post(post_url, data=post_data, stream=True, timeout=(10, 60))
        file_response.raise_for_status()

        content_disposition = file_response.headers.get('content-disposition', '')
        filename = extract_filename(content_disposition) or "teslim_edilen_dosya.zip"
        sanitized = sanitize_filename(filename)
        
        file_path = join(destination_folder, sanitized)
        
        if exists(file_path):
            logger.verbose(f"Teslim edilen dosya '{file_path}' zaten mevcut. Atlanıyor.")
            return

        with open(file_path, "wb") as f:
            f.write(file_response.content)
        
        logger.new_file(file_path)

    except Exception as e:
        logger.error(f"Postback ile dosya indirilirken hata oluştu: {e}")


def archive_homeworks_for_course(course: Course, session: requests.Session, download_file_func: Callable):
    """
    Fetches, parses, and saves all homeworks, their details, and associated files for a given course.
    """
    logger.verbose(f"'{course.code} (CRN: {course.crn})' için ödevler arşivleniyor...")

    unique_folder_name = f"{course.code} (CRN {course.crn})"
    sanitized_folder_name = sanitize_filename(unique_folder_name)
    course_base_path = join(globals.BASE_PATH, sanitized_folder_name)
    
    homeworks_path = join(course_base_path, sanitize_filename("Ödevler"))
    os.makedirs(homeworks_path, exist_ok=True)

    homework_list_url = URL + course.link.strip() + HOMEWORK_URL_EXTENSION
    
    try:
        logger.debug(f"Ödev listesi sayfası isteniyor: {homework_list_url}")
        response = session.get(homework_list_url)
        response.raise_for_status()
        
        if "debug" in globals.ARGV:
            _dump_html_for_debug(course.crn, response, "Homework_List")

        _parse_and_save_homeworks(response, homeworks_path, course, session, download_file_func)

    except requests.exceptions.RequestException as e:
        logger.error(f"'{course.code}' dersi için ödevler alınırken HTTP hatası oluştu: {e}")
    except Exception as e:
        logger.error(f"'{course.code}' dersi için ödevler işlenirken beklenmedik bir hata oluştu: {e}")


def _parse_and_save_homeworks(list_page_response: requests.Response, destination_folder: str, course: Course, session: requests.Session, download_file_func: Callable):
    """
    Parses the homework list page, visits each homework's detail page,
    and saves the content and files.
    """
    list_soup = BeautifulSoup(list_page_response.text, "lxml")
    homework_items = list_soup.select("table.data td")
    
    if not homework_items:
        logger.verbose(f"CRN {course.crn} için 'table.data td' yapısında ödev bulunamadı.")
        return

    logger.verbose(f"{len(homework_items)} adet potansiyel ödev bulundu.")

    for item in homework_items:
        try:
            detail_link_element = item.find("a", string=re.compile(r"Ödevi Görüntüle"))
            if not detail_link_element or not detail_link_element.has_attr('href'):
                continue

            detail_page_url = URL + detail_link_element['href']
            detail_response = session.get(detail_page_url)
            detail_response.raise_for_status()

            if "debug" in globals.ARGV:
                try:
                    homework_id = detail_link_element['href'].split('/')[-1]
                    _dump_html_for_debug(course.crn, detail_response, f"Homework_Detail_{homework_id}")
                except Exception as e:
                    logger.warning(f"Could not dump homework detail HTML: {e}")

            detail_soup = BeautifulSoup(detail_response.text, 'lxml')

            container = detail_soup.select_one("div.orta > div.ic")
            if not container:
                logger.warning(f"Ödev detay sayfasında ana içerik konteyneri ('div.orta > div.ic') bulunamadı: {detail_page_url}")
                continue
                
            detail_title_element = container.select_one("h1")
            if not detail_title_element:
                logger.warning(f"Ödev başlığı ('h1') bulunamadı: {detail_page_url}")
                continue

            title = fix_turkish_characters(detail_title_element.get_text(strip=True))
            sanitized_title = sanitize_filename(title)
            
            homework_specific_folder = join(destination_folder, sanitized_title)
            os.makedirs(homework_specific_folder, exist_ok=True)

            info_file_path = join(homework_specific_folder, "detaylar.txt")
            if not exists(info_file_path):
                form_div = container.select_one("div.form2")
                if form_div:
                    deadlines_text = "Tarih bilgisi bulunamadı."
                    deadline_table = form_div.find("table")
                    if deadline_table:
                        deadlines_text = fix_turkish_characters(deadline_table.get_text("\n", strip=True))

                    description_text = "Açıklama bulunamadı."
                    desc_title = form_div.find("span", class_="title_field", string=re.compile("Ödev Açıklaması", re.I))
                    if desc_title:
                        desc_content = desc_title.find_next_sibling("span", class_="data_field")
                        if desc_content:
                            description_text = fix_turkish_characters(desc_content.get_text("\n", strip=True))

                    with open(info_file_path, "w", encoding="utf-8") as f:
                        f.write(f"Ödev Detayları: {title}\n" + "="*40 + "\n")
                        f.write(f"{deadlines_text}\n\n")
                        f.write("--- Açıklama ---\n" + f"{description_text}\n")
                    logger.new_file(info_file_path)
                else:
                    logger.warning(f"Ödev detayları için 'div.form2' bulunamadı: {detail_page_url}")

            kaynak_dosyalar_header = container.find("h2", string=lambda t: t and "Kaynak Dosyalar" in fix_turkish_characters(t))
            if kaynak_dosyalar_header:
                table_container = kaynak_dosyalar_header.find_next_sibling("div")
                if table_container:
                    table = table_container.find("table", class_="data")
                    if table:
                        for link in table.select("a[href]"):
                            download_file_func(URL + link['href'], homework_specific_folder)

            submitted_files_link = None
            for a_tag in container.select('a[href]'):
                link_text = fix_turkish_characters(a_tag.get_text(strip=True))
                if "Yüklediğiniz ödev dosyalarını indirin" in link_text:
                    submitted_files_link = a_tag
                    break
            
            if submitted_files_link:
                href = submitted_files_link['href']
                if 'javascript:__doPostBack' in href:
                    _handle_postback_download(detail_soup, session, href, homework_specific_folder)
                else:
                    download_file_func(URL + href, homework_specific_folder)

        except Exception as e:
            error_url_part = "Bilinmeyen URL"
            if 'detail_page_url' in locals():
                error_url_part = detail_page_url
            logger.warning(f"Bir ödev ({error_url_part}) işlenirken hata oluştu, atlanıyor: {e}")
            continue