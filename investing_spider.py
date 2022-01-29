#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @time: 2022/1/29 12:16 上午
"""
using uc to bypass cloudflare solution

https://github.com/ultrafunkamsterdam/undetected-chromedriver
"""
import copy
import logging
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from bs4 import BeautifulSoup
from selenium import webdriver
import threadpool
import undetected_chromedriver.v2 as uc


logging.basicConfig(level=logging.INFO)
coin_pair_file_path = 'stop_coins.conf'
homeurl = 'https://www.investing.com/crypto/currencies'
baseurl = 'https://cn.investing.com/crypto/{coin}/{pair}-technical'
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")


def crawl_coin_pairs():
    noptions = copy.deepcopy(options)
    try:
        driver = uc.Chrome(options=noptions)
        driver.get(homeurl)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
    finally:
        driver.stop()
    coin_tr_eles = soup('table')[0]('tbody')[0].find_all('tr')
    assert len(coin_tr_eles) == 100, 'should be {} coins'.format(len(coin_tr_eles))
    coin_pairs = []
    for coin_tr in coin_tr_eles:
        td_eles = coin_tr.find_all('td')
        rank = td_eles[0].string
        try:
            symbol = td_eles[2]('a')[0].attrs['href'].split('/')[-1]
        except Exception:
            logging.warning('cannot analysis {}'.format(coin_tr))
            continue
        coinid = td_eles[3].string
        pair = '{}-usd'.format(coinid.lower())
        url = baseurl.format(coin=symbol, pair=pair)
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


def get_start_driver(url):
    noptions = copy.deepcopy(options)
    driver = uc.Chrome(options=noptions)
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    return driver, soup


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


def ayns_crawl(coin_pairs):
    batch_pairs_signal = {}
    for coin_pair in coin_pairs:
        logging.info('running {}'.format(coin_pair))
        rank, coin_pair, url = coin_pair
        try:
            driver, soup = get_start_driver(url)
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
        finally:
            driver.stop()
        logging.info('finish crawling {}'.format(batch_pairs_signal))
    return batch_pairs_signal


def main(batch_size=10, pool_size=10):
    coin_pairs = crawl_coin_pairs()
    logging.info('read {} coin pair from file.'.format(len(coin_pairs)))
    investing_spider_coin_pairs_signal = {'data': {}}

    args = [coin_pairs[idx: idx+batch_size] for idx in range(0, len(coin_pairs), batch_size)]
    start_time = time.time()
    pool = threadpool.ThreadPool(pool_size)
    requests = threadpool.makeRequests(ayns_crawl, args)
    [pool.putRequest(req) for req in requests]
    pool.wait()
    logging.info('Finish using {} second'.format(time.time() - start_time))

    localtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    investing_spider_coin_pairs_signal['time'] = localtime
    investing_spider_coin_pairs_signal['code'] = 'OK'
    logging.info(investing_spider_coin_pairs_signal)
    return investing_spider_coin_pairs_signal


if __name__ == '__main__':
    # https://apscheduler.readthedocs.io/en/latest/modules/triggers/interval.html?highlight=add_job
    scheduler = BlockingScheduler()
    start_date = '2022-01-29 10:00:00'
    interval = 10
    scheduler.add_job(main, 'interval', minutes=interval, start_date=start_date)
    scheduler.start()
    logging.info('Starting scheduler success, every {} minutes from {}'.format(interval, start_date))
