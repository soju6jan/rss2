# -*- coding: utf-8 -*-
#########################################################
# python
import os
from datetime import datetime, timedelta
import traceback
import logging
import json
import time
import threading

# third-party
from pytz import timezone
import sqlite3
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_

# sjva 공용
from framework import app, db, scheduler, path_data, celery
from framework.job import Job
from framework.util import Util
from system.logic import SystemLogic

# 패키지
from .plugin import logger, package_name
from .logic_from_site import LogicFromSite
from .model import ModelSetting, ModelScheduler2, ModelBbs2,  ModelGroup2
import telegram_bot
from .logic_self import LogicSelf

#########################################################

class Logic(object):
    db_default = { 
        'db_version' : '1',
        'auto_start' : 'False',
        'interval' : '10',
        'feed_count' : '100',
        'default_torrent_mode' : 'magnet',
        'web_page_size' : '30', 
        'site_info_url' : '',
        'use_proxy' : 'False',
        'proxy_url' : '',
        'recent_code_self' : '',
        'recent_code_bot' : '',
        'use_torrent_info' : 'False', 
        'test_count' : '3',
        'max_page' : '5',
    }
    

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            # DB 초기화
            Logic.db_init()

            if ModelSetting.get_bool('auto_start'):
                Logic.scheduler_start()

            # 편의를 위해 json 파일 생성
            from plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def scheduler_start():
        try:
            job = Job(package_name, package_name, ModelSetting.get('interval'), Logic.scheduler_function, u"토렌트 사이트 크롤링", True)
            scheduler.add_job_instance(job)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_stop():
        try:
            scheduler.remove_job(package_name)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_function():
        if app.config['config']['use_celery']:
            result = LogicSelf.scheduler_function_task.apply_async()
            result.get()
        else:
            LogicSelf.scheduler_function_task()

    @staticmethod
    def reset_db():
        try:
            #db.session.query(ModelDownloaderMovieItem).delete()
            #db.session.commit()
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
    
    @staticmethod
    def one_execute():
        try:
            if scheduler.is_include(package_name):
                if scheduler.is_running(package_name):
                    ret = 'is_running'
                else:
                    scheduler.execute_job(package_name)
                    ret = 'scheduler'
            else:
                def func():
                    time.sleep(2)
                    Logic.scheduler_function()
                threading.Thread(target=func, args=()).start()
                ret = 'thread'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
        return ret

    # 기본 구조 End
    ##################################################################

     