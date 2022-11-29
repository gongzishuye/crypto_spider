#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @time: 2022/1/29 12:16 上午
"""
using uc to bypass cloudflare solution

https://github.com/ultrafunkamsterdam/undetected-chromedriver
"""
import copy
import collections
import datetime
import gc
import json
import logging
import os
import time
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from bs4 import BeautifulSoup
from selenium import webdriver
import threadpool
# from multiprocessing import Pool
import undetected_chromedriver.v2 as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from pympler import muppy, summary
import objgraph


def print_mem():
    objgraph.show_most_common_types(limit=50)


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
TIME_PERIOD_KV = {
    '5分钟': 'min_5',
    '15分钟': 'min_15',
    '30分钟': 'min_30',
    '每小时': 'hour_1',
    '5小时': 'hour_5',
    '每日': 'day_1',
    '每周': 'week_1',
}


def create_options():
    options = uc.ChromeOptions()
    options.add_argument('--headless') # 开启无界面模式
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
        rank = td_eles[0].text
        try:
            coinid = td_eles[2]('a')[0].attrs['href'].split('/')[-1]
        except Exception:
            logger.warning('cannot analysis {}'.format(coin_tr))
            continue
        if coinid in coin_sym_kv:
            symbol = coin_sym_kv[coinid]
        else:
            symbol = td_eles[3].text
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
    cur_price = price_spans[0].text
    today_chg = price_spans[3].text
    print(cur_price, today_chg)

    price_wave_ele = soup.find('div', attrs={'id': 'quotes_summary_secondary_data'})
    wave_span_eles = price_wave_ele.find_all('li')[2].find_all('span')[1].find_all('span')
    price_low = wave_span_eles[0].text
    price_high = wave_span_eles[1].text
    print(price_low, price_high)
    return cur_price, today_chg, price_low, price_high


def get_start_driver():
    noptions = create_options()
    driver = uc.Chrome(version_main=97, executable_path=executable_path, headless=True, options=noptions)
    return driver


def _get_signal(soup):
    tech_content = soup.find('div', attrs={'id': 'techStudiesInnerWrap'})
    conclusion_div, emv_div, tech_div = tech_content.find_all('div')
    conclusion = conclusion_div('span')[0].text
    return conclusion


def get_investing_coin_pair_signal(driver):
    investing_signal_lst = []
    timePeriodsWidget = driver.find_element_by_id('timePeriodsWidget')
    time_period_eles = timePeriodsWidget.find_elements_by_tag_name('li')
    periods = []
    for time_period_ele in time_period_eles:
        time_period = time_period_ele.text
        if time_period == '1 分钟' or time_period == '每月':
            continue
        # periods.append(time_period_ele.text)

    # for time_period in periods:
    #     print(f'running {time_period}')
    #     if time_period == '1 分钟' or time_period == '每月':
    #         continue

    #     timePeriodsWidget = driver.find_element_by_id('timePeriodsWidget')
    #     time_period_eles = timePeriodsWidget.find_elements_by_tag_name('li')
    #     for time_period_ele in time_period_eles:
    #         if time_period_ele.text == time_period:
    #             break
        taga = time_period_ele.find_element_by_tag_name('a')
        driver.execute_script("arguments[0].click();", taga)
        # driver.refresh()

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        signal = _get_signal(soup)
        try:
            single_signal = {}
            single_signal['type'] = TIME_PERIOD_KV[time_period.replace(' ','')]
            single_signal['state'] = signal
            investing_signal_lst.append(single_signal)
        except KeyError:
            continue
    return investing_signal_lst


def ayns_crawl(coin_pairs):
    pair_signal_lst = []
    driver = get_start_driver()
    for idx, coin_pair in enumerate(coin_pairs):
        st = time.time()
        logger.info('running {} : {}'.format(idx, coin_pair))
        print('running {}'.format(coin_pair))
        st = time.time()
        rank, coin_pair, url = coin_pair
        try:
            driver.get(url)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            cur_price, today_chg, price_low, price_high = get_price(soup)
            print('running', url)
            investing_signal_lst = get_investing_coin_pair_signal(driver)
            coin_pair_signal = {
                'investing_signal': investing_signal_lst,
                'cur_price': cur_price,
                'today_chg': today_chg,
                'price_low': price_low,
                'price_high': price_high,
                'rank': rank,
                'name': coin_pair,
            }
            pair_signal_lst.append(coin_pair_signal)
            logger.info(coin_pair_signal)
            print(coin_pair_signal)
            print('Finish using {} second'.format(time.time() - st))
        except AttributeError as e:
            logger.error('{} is failed.'.format(e))
            continue
        except Exception as e:
            logger.error('{} failed for other reasons {}.'.format(url, e))
            continue
    duration = time.time() - st
    logger.info('finish crawling {} cost {}s'.format(pair_signal_lst, duration))
    driver.quit()
    print('finish crawling {} cost {}s'.format(pair_signal_lst, duration))
    return pair_signal_lst


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
    logger.info('read {} coin pair from home page.'.format(len(coin_pairs)))
    print('read {} coin pair from home page.'.format(len(coin_pairs)))

    args = [coin_pairs[idx: idx+batch_size] for idx in range(0, len(coin_pairs), batch_size)]
    pool = threadpool.ThreadPool(pool_size)
    requests = threadpool.makeRequests(ayns_crawl, args, save_result)
    [pool.putRequest(req) for req in requests]
    pool.wait()
    logger.info('Finish using {} second'.format(time.time() - st))


if __name__ == '__main__':
    # https://apscheduler.readthedocs.io/en/latest/modules/triggers/interval.html?highlight=add_job
    # scheduler = BlockingScheduler(timezone='Asia/Shanghai')
    # interval = 30
    # scheduler.add_job(main, 'interval', minutes=interval, max_instances=1, next_run_time=datetime.datetime.now())
    # scheduler.start()
    # logger.info('Starting scheduler success, every {} minutes from {}'.format(interval, start_date))
    main()

