#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# @time: 2022/1/29 3:38 下午
from collections import OrderedDict
import json
import logging
import glob
import datetime

from flask import Flask, jsonify
from flask_cors import CORS


logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config ['JSON_SORT_KEYS'] = False
CORS(app, supports_credentials=True)


@app.route('/coin_signal', methods=['POST', 'GET'])
def crawl_signal():
    today_date = datetime.datetime.now().strftime('%Y-%m-%d')
    try:
        files = glob.glob('database/{}/*'.format(today_date))
        if len(files) == 0:
            yesterday = (datetime.datetime.now()-datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            files = glob.glob('database/{}/*'.format(yesterday))
        files.sort()
        target_file = files[-1]
        result = json.load(open(target_file, encoding='utf-8'), object_pairs_hook=OrderedDict)
        logging.info('resp [{}] for this request.'.format(target_file))
    except Exception as ex:
        logging.error(ex)
        return jsonify({'code': -1})
    return jsonify(result)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8888)

