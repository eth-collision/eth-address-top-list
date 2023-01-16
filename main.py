from selenium import webdriver
from bs4 import BeautifulSoup
import time

options = webdriver.FirefoxOptions()
options.add_argument("--enable-javascript")
options.add_argument("--enable-cookies")
options.add_argument("--headless")
browser = webdriver.Firefox(options=options)

for i in range(1, 101):
    url = "https://etherscan.io/accounts/" + str(i) + "?ps=100"
    print(url)

    browser.get(url)
    # skip couldflare
    time.sleep(3)

    html_source = browser.page_source
    html_soup: BeautifulSoup = BeautifulSoup(html_source, 'html.parser')

    info = html_soup.find_all("a")
    for list in info:
        for l in list:
            t = l.get_text()
            if t.startswith("0x"):
                with open("address.txt", "a") as file:
                    file.write(t + "\n")

