from src import logger

try:
    from bs4 import BeautifulSoup
    import requests
except ModuleNotFoundError:
    logger.fail(
        "Gerekli kütüphaneler eksik. Yüklemek için 'pip install -r requirements.txt' komutunu çalıştırın."
    )

URL = "https://ninova.itu.edu.tr"


def check_connection() -> bool:
    CHECK_CONNECTIVITY_URL = "http://www.example.com/"
    try:
        requests.get(CHECK_CONNECTIVITY_URL)
        return True
    except:
        return False


def login(user_secure_info: tuple) -> requests.Session:
    global URL
    _URL = URL + "/Kampus1"
    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:104.0) Gecko/20100101 Firefox/104.0",
    }

    # Sayfayı isteyip parse etme
    session = requests.Session()
    try:
        page = session.get(_URL, headers=HEADERS)
    except:
        logger.warning("Ninova sunucusuna bağlanılamadı.")
        if check_connection():
            logger.fail("İnternet var ancak Ninova'ya bağlanılamıyor.")
        else:
            logger.fail("İnternete erişim yok. Bağlantınızı kontrol edin.")

    page = BeautifulSoup(page.content, "lxml")

    post_data = dict()
    for field in page.find_all("input"):
        post_data[field.get("name")] = field.get("value")
    post_data["ctl00$ContentPlaceHolder1$tbUserName"] = user_secure_info[0]
    post_data["ctl00$ContentPlaceHolder1$tbPassword"] = user_secure_info[1]

    page = _login_request(session, post_data, page)

    page = BeautifulSoup(page.content, "lxml")
    if page.find(id="ctl00_Header1_tdLogout") is None:
        raise PermissionError("Kullanıcı adı veya şifre yanlış!")
    return session

@logger.speed_measure("Giriş yapma", False, False)
def _login_request(session: requests.Session, post_data: dict, page: BeautifulSoup):
    page = session.post(
        "https://girisv3.itu.edu.tr" + page.form.get("action")[1:], data=post_data
    )
    return page

# Fonksiyon debug isimleri