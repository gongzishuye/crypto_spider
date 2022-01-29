#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @time: 2022/1/29 3:38 下午
import json
import logging
import os
import time

from flask import Flask, jsonify


logging.basicConfig(level=logging.INFO)
app = Flask(__name__)


@app.route('/coin_signal', methods=['POST', 'GET'])
def crawl_signal():
    today_date = time.strftime("%Y-%m-%d", time.localtime())
    files = os.listdir('database/{}'.format(today_date))
    files.sort()
    target_file = files[-1]
    result = json.load(open(target_file, encoding='utf-8'))
    logging.info('resp [{}] for this request.'.format(target_file))
    return jsonify(result)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8880)
