#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @time: 2022/1/29 12:16 上午
"""
using uc to bypass cloudflare solution

https://github.com/ultrafunkamsterdam/undetected-chromedriver
"""
import copy
import datetime
import json
import logging
import os
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from bs4 import BeautifulSoup
from selenium import webdriver
import threadpool
# from multiprocessing import Pool
import undetected_chromedriver.v2 as uc


logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)
handler = logging.FileHandler('log.txt')
handler.setLevel(logging.INFO)
logger.addHandler(handler)
stop_coins_file_path = 'stop_coins.conf'
custom_coins_file_path = 'custom_tokens.conf'
executable_path='/root/.local/share/undetected_chromedriver/chromedriver'
homeurl = 'https://www.investing.com/crypto/currencies'
baseurl = 'https://cn.investing.com/crypto/{coin}/{pair}-technical'


def create_options():
    options = webdriver.ChromeOptions()
    # options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument('--headless') # 开启无界面模式
    options.add_argument('--disable-gpu') # 禁用显卡
    # options.add_argument("--disable-blink-features=AutomationControlled")
    # options.debugger_address = 'localhost:15248'
    return options


def read_custom_coins():
    coin_pairs = open(custom_coins_file_path).read().strip().split('\n')
    coin_sym_kv = {}
    for coin_pair in coin_pairs:
        coin, symbol = coin_pair.split(' ')
        coin_sym_kv[coin] = symbol
    return coin_sym_kv


def read_stop_coin():
    coin_pairs = open(stop_coins_file_path).read().strip().split('\n')
    return set(coin_pairs)


def crawl_coin_pairs():
    noptions = create_options()
    try:
        driver = uc.Chrome(version_main=97, executable_path=executable_path, headless=True, option=noptions)
        driver.get(homeurl)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
    finally:
        driver.quit()
    coin_tr_eles = soup('table')[0]('tbody')[0].find_all('tr')
    logger.info('Total have {} coins'.format(len(coin_tr_eles)))
    coin_tr_eles = coin_tr_eles[:100]
    coin_pairs = []
    stop_coin_pairs = read_stop_coin()
    coin_sym_kv = read_custom_coins()
    for coin_tr in coin_tr_eles:
        td_eles = coin_tr.find_all('td')
        rank = td_eles[0].string
        try:
            coinid = td_eles[2]('a')[0].attrs['href'].split('/')[-1]
        except Exception:
            logger.warning('cannot analysis {}'.format(coin_tr))
            continue
        if coinid in coin_sym_kv:
            symbol = coin_sym_kv[coinid]
        else:
            symbol = td_eles[3].string
        pair = '{}-usd'.format(symbol.lower())
        if pair in stop_coin_pairs:
            continue
        url = baseurl.format(coin=coinid, pair=pair)
        coin_pairs.append((rank, pair, url))
    return coin_pairs


def get_price(soup):
    price_ele = soup.find('div', attrs={'class': 'top bold inlineblock'})
    price_spans = price_ele.find_all('span')
    assert len(price_spans) == 4, 'page html arange change'
    cur_price = price_spans[0].string
    today_chg = price_spans[3].string
    print(cur_price, today_chg)

    price_wave_ele = soup.find('div', attrs={'id': 'quotes_summary_secondary_data'})
    wave_span_eles = price_wave_ele.find_all('li')[2].find_all('span')[1].find_all('span')
    price_low = wave_span_eles[0].string
    price_high = wave_span_eles[1].string
    print(price_low, price_high)
    return cur_price, today_chg, price_low, price_high


def get_start_driver():
    noptions = create_options()
    driver = uc.Chrome(version_main=97, executable_path=executable_path, headless=True, options=noptions)
    # driver.get(url)
    # soup = BeautifulSoup(driver.page_source, 'html.parser')
    # return driver, soup
    return driver


def _get_signal(soup):
    tech_content = soup.find('div', attrs={'id': 'techStudiesInnerWrap'})
    conclusion_div, emv_div, tech_div = tech_content.find_all('div')
    conclusion = conclusion_div('span')[0].string
    return conclusion


def get_investing_coin_pair_signal(driver):
    investing_signal = {}

    timePeriodsWidget = driver.find_element_by_id('timePeriodsWidget')
    time_period_eles = timePeriodsWidget.find_elements_by_tag_name('li')
    for time_period_ele in time_period_eles:
        time_period = time_period_ele.text
        print(f'runing {time_period}')
        taga = time_period_ele.find_element_by_tag_name('a')
        driver.execute_script("arguments[0].click();", taga)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        signal = _get_signal(soup)
        investing_signal[time_period] = signal
    return investing_signal


def ayns_crawl(coin_pairs, driverid=0):
    batch_pairs_signal = {}
    driver = get_start_driver()
    for coin_pair in coin_pairs:
        logger.info('running {}'.format(coin_pair))
        st = time.time()
        rank, coin_pair, url = coin_pair
        try:
            driver.get(url)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            cur_price, today_chg, price_low, price_high = get_price(soup)
            investing_signal = get_investing_coin_pair_signal(driver)
            coin_pair_signal = {
                'investing_signal': investing_signal,
                'cur_price': cur_price,
                'today_chg': today_chg,
                'price_low': price_low,
                'price_high': price_high,
            }
            batch_pairs_signal[coin_pair] = coin_pair_signal
        except AttributeError:
            logger.error('{} is failed.'.format(url))
            continue
        except Exception:
            logger.error('{} failed for other reasons.'.format(url))
            continue
        duration = time.time() - st
    logger.info('finish crawling {} cost {}s'.format(batch_pairs_signal, duration))
    driver.quit()
    return batch_pairs_signal


def save_result(request, result):
    investing_spider_coin_pairs_signal = {'data': result}
    localtime = time.strftime("%Y%m%d%H%M%S", time.localtime())
    today = time.strftime("%Y-%m-%d", time.localtime())
    dir_path = 'database/{}'.format(today)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    investing_spider_coin_pairs_signal['time'] = localtime
    investing_spider_coin_pairs_signal['code'] = 0
    output_file = os.path.join(dir_path, '{}.log'.format(localtime))
    with open(output_file, 'w', encoding='utf-8') as fin:
        json.dump(investing_spider_coin_pairs_signal, fin, ensure_ascii=True)
    logger.info(investing_spider_coin_pairs_signal)
    logger.info('Finish save file: {}.'.format(output_file))


def main(batch_size=100, pool_size=1):
    st = time.time()
    coin_pairs = crawl_coin_pairs()
    logger.info('read {} coin pair from file.'.format(len(coin_pairs)))

    args = [coin_pairs[idx: idx+batch_size] for idx in range(0, len(coin_pairs), batch_size)]
    pool = threadpool.ThreadPool(pool_size)
    requests = threadpool.makeRequests(ayns_crawl, args, save_result)
    [pool.putRequest(req) for req in requests]
    pool.wait()
    logger.info('Finish using {} second'.format(time.time() - st))


if __name__ == '__main__':
    # https://apscheduler.readthedocs.io/en/latest/modules/triggers/interval.html?highlight=add_job
    scheduler = BlockingScheduler()
    interval = 15
    scheduler.add_job(main, 'interval', minutes=interval, max_instances=1, next_run_time=datetime.datetime.now())
    scheduler.start()
    logger.info('Starting scheduler success, every {} minutes from {}'.format(interval, start_date))

