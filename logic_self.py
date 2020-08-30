# -*- coding: utf-8 -*-
#########################################################
# python
import os
from datetime import datetime, timedelta
import traceback
import logging
import json
import time

# third-party
from pytz import timezone
import sqlite3
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, path_data, celery
from framework.job import Job
from framework.util import Util
from system.logic import SystemLogic
from system.model import ModelSetting as SystemModelSetting

# 패키지
from .plugin import logger, package_name
from .logic_from_site import LogicFromSite
from .model import ModelSetting, ModelScheduler2, ModelBbs2, ModelGroup2, ModelSite2

#########################################################

class LogicSelf(object):

    #########################################################
    # Site 관리
    #########################################################
    # 문자열에서 사이트 정보를 뽑아라
    @staticmethod
    def parse_site_info_from_string(data):
        try:
            tmp = data.split('\n')
            flag = False
            target = []
            for t in tmp:
                t = t.strip()
                if t == '# JSON_START':
                    flag = True
                    continue
                elif t == '# JSON_END':
                    break
                elif t.startswith('#'):
                    continue
                else:
                    if flag:
                        target.append(t)
            target = ''.join(target)
            ret = json.loads(target)
            return ret
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc()) 

    @staticmethod
    def site_edit(req):
        try:
            site_id = req.form['modal_site_id']
            modal_site_json = req.form['modal_site_json']
            info = json.loads(modal_site_json.decode('utf8'))
            entity = ModelSite2.get(site_id=site_id)
            if entity is not None:
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(entity, "info")
                entity.info = info
                entity.name = info['NAME']
                db.session.add(entity)
                db.session.commit()
                return 'edit_success'
            else:
                tmp = ModelSite2.get(name=info['NAME'])
                if tmp:
                    return 'exist'
                else:
                    entity = ModelSite2("my", info, u"직접 입력")
                    db.session.add(entity)
                    db.session.commit()
                    return 'add_success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc()) 
            return 'exception'

    #########################################################


    #########################################################
    # 스케쥴링 관련
    #########################################################
    @staticmethod   
    def add_scheduler(req):
        try:
            scheduler_id = int(req.form['modal_scheduler_id'])
            if scheduler_id == -1:
                site_id = req.form['site_id_select'].strip()
                board_id = req.form['board_id'].strip()
                instance = ModelScheduler2.get(site_id, board_id)
                if instance is not None:
                    return 'already_exist'
                site_instance = ModelSite2.get(site_id)
                entity = ModelScheduler2(site_instance)
                entity.board_id = board_id
                entity.include_scheduler = (req.form['include_scheduler'] == 'True')
                entity.use_proxy = (req.form['use_proxy'] == 'True')
                entity.use_torrent_info = (req.form['use_torrent_info'] == 'True')
                entity.priority = int(req.form['priority'])
                entity.scheduler_interval = int(req.form['scheduler_interval'])
                db.session.add(entity)
                db.session.commit()
                return 'success'
            else:
                entity = db.session.query(ModelScheduler2).filter_by(id=scheduler_id).with_for_update().first()
                if entity:
                    entity.include_scheduler = (req.form['include_scheduler'] == 'True')
                    entity.use_proxy = (req.form['use_proxy'] == 'True')
                    entity.use_torrent_info = (req.form['use_torrent_info'] == 'True')
                    entity.priority = int(req.form['priority'])
                    entity.scheduler_interval = int(req.form['scheduler_interval'])
                    db.session.commit()
                    return 'success_update'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'

    @staticmethod
    def get_scheduler_list():
        try:
            ret = []
            items = ModelScheduler2.get_list()
            for item in items:
                last = item.get_last_bbs()
                tmp = item.as_dict()
                tmp['last'] = last.as_dict() if last is not None else None
                tmp['broad_url'] = LogicFromSite.get_board_url(item.site, item.board_id, 1)
                tmp['site'] = item.site.as_dict()
                tmp['api'] = '%s/%s/api/board/%s/%s' % (SystemModelSetting.get('ddns'), package_name, item.site.name, item.board_id)
                if SystemModelSetting.get_bool('auth_use_apikey'):
                    tmp['api']  += '?apikey=%s' % SystemModelSetting.get('auth_apikey')
                if last is not None:
                    tmp['one_day_more'] = (last.created_time < datetime.now() + timedelta(days=-1))
                ret.append(tmp)
            return ret
            
            #return ModelScheduler2.get_list(by_dict=True)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())  


    @staticmethod
    def remove_scheduler(req):
        try:
            db_id = req.form['db_id']
            LogicSelf.remove_scheduler_db_from_id(db_id)
            item = db.session.query(ModelScheduler2).filter_by(id=db_id).first()
            if item is not None:
                db.session.delete(item)
                db.session.commit()
            return 'success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc()) 
            return 'fail'
    

    @staticmethod
    def remove_scheduler_db_from_id(db_id):
        try:
            item = db.session.query(ModelScheduler2).filter_by(id=db_id).first()
            if item is not None:
                bbs_query = db.session.query(ModelBbs2.id).filter(ModelBbs2.site == item.sitename).filter(ModelBbs2.board==item.board_id)
                bbs_query.delete()
                db.session.commit()
            return 'success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc()) 
            return 'fail'
    #########################################################


    #########################################################
    # 그룹 관련
    #########################################################
    @staticmethod
    def get_group_list():
        try:
            lists = ModelGroup2.get_list(by_dict=True)
            for item in lists:
                item['rss'] = '%s/%s/api/group/%s' % (SystemModelSetting.get('ddns'), package_name, item['groupname'])
                if SystemModelSetting.get_bool('auth_use_apikey'):
                    item['rss'] += '?apikey=%s' % SystemModelSetting.get('auth_apikey')
            return lists
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def add_group(req):
        try:
            groupname = req.form['groupname']
            entity = db.session.query(ModelGroup2).filter_by(groupname=groupname).first()
            if entity is not None:
                return 'already_exist'
            entity = ModelGroup2()
            entity.groupname = groupname
            db.session.add(entity)
            db.session.commit()
            return 'success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'
    
    @staticmethod
    def remove_group(req):
        try:
            group_id = req.form['group_id']
            entity = db.session.query(ModelGroup2).filter_by(id=group_id).first()
            if entity is not None:
                db.session.delete(entity)
                db.session.commit()
            else:
                return 'not_exist'
            return 'success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'

    @staticmethod
    def add_group_child(req):
        try:
            group_id = req.form['group_id']
            sitename = req.form['sitename']
            boardname = req.form['boardname']

            entity = db.session.query(ModelScheduler2).filter_by(sitename=sitename, board_id=boardname).first()
            
            group_entity = db.session.query(ModelGroup2).filter_by(id=group_id).with_for_update().first()

            if entity in group_entity.schedulers:
                return 'already_exist'
            group_entity.schedulers.append(entity)
            db.session.add(group_entity)
            db.session.commit()
            return 'success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'

    @staticmethod
    def remove_group_child(req):
        try:
            group_id = req.form['group_id']
            child_id = req.form['child_id']
            group_entity = db.session.query(ModelGroup2).filter_by(id=group_id).with_for_update().first()

            child_entity = db.session.query(ModelScheduler2).filter_by(id=child_id).first()

            if child_entity in group_entity.schedulers:
                group_entity.schedulers.remove(child_entity)
                db.session.commit()
            else:
                return 'not_exist'
            return 'success'
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return 'fail'


    @staticmethod
    def get_search_form_info():
        try:
            ret = {}
            items = db.session.query(ModelScheduler2).filter().all()
            ret['group'] = LogicSelf.get_group_list()
            ret['site'] = []
            ret['board'] = {}
            for item in items:
                if item.sitename not in ret['site']:
                    ret['site'].append(item.sitename)
                    ret['board'][item.sitename] = []
                if item.board_id not in ret['board'][item.sitename]:
                    ret['board'][item.sitename].append(item.board_id)
            return ret
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc()) 
    
    #########################################################



    #########################################################
    # UI 관련
    #########################################################
    @staticmethod
    def action_test(req):
        try:
            site_id = req.form['site_id'].strip()
            board_id = req.form['board_id'].strip()
            site_instance = ModelSite2.get(site_id=site_id)
            rss_list = LogicFromSite.get_list(site_instance, board_id, max_count=ModelSetting.get_int('test_count'))
            return rss_list
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    #########################################################




    @staticmethod
    @celery.task
    def scheduler_function_task():
        try:
            logger.debug('RSS scheduler_function')
            items = ModelScheduler2.get_list()
            for item in items:
                logger.debug(u'스케쥴링 시작')
                logger.debug('%s %s', item.sitename, item.board_id)
                if item.site is None:
                    continue
                if not item.include_scheduler:
                    logger.debug('not include_scheduler')
                    continue
                if item.scheduler_interval is None or item.scheduler_interval <= 1:
                    pass
                else:
                    scheduler_count = ModelSetting.get_int('scheduler_count')
                    logger.debug('scheduler_count:%s', scheduler_count)
                    if (scheduler_count % item.scheduler_interval) != 0:
                        logger.debug("scheduler_interval : %s", item.scheduler_interval)
                        continue

                if 'USING_BOARD_CHAR_ID' not in item.site.info['EXTRA']:
                    last_bbs = item.get_last_bbs()
                    if last_bbs is not None:
                        max_id = last_bbs.board_id
                    else:
                        max_id = 0
                else:
                    max_id = 0
                rss_list = LogicFromSite.get_list(item.site, item.board_id, max_id=max_id, page=ModelSetting.get_int('max_page'), scheduler_instance=item)
                if rss_list:
                    save_list = LogicSelf.__db_save_list(item.site, item, rss_list)
                    #logger.debug(save_list)

                    groups = LogicSelf.get_group_list()
                    group_name = None
                    for group in groups:
                        for sched in group['schedulers']:
                            if sched['sitename'] == item.sitename and sched['board_id'] == item.board_id:
                                group_name = group['groupname']
                                break
                        if group_name is not None:
                            break
                    
                    from framework.common.torrent.process import TorrentProcess
                    TorrentProcess.server_process(save_list, category=group_name)


            # selenium이 celery에서 돌 경우 해제안됨.
            from system import SystemLogicSelenium
            SystemLogicSelenium.close_driver()
                        
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    # 역순으로
    @staticmethod
    def __db_save_list(site_instance, scheduler_instance, rss_list):
        
        ret = []
        for item in reversed(rss_list):
            #logger.debug('ID : %s', item['id'])
            #logger.debug('TITLE : %s', item['title'])
            # no 마그넷인 경우 제외하고 마그넷이 없으면 패스
            if 'ONLY_FILE' in site_instance.info['EXTRA']:
                pass
            else:
                if 'magnet' not in item or not item['magnet']:
                    continue
            try:
                # board, board_id, site
                
                bbs = ModelBbs2(scheduler_instance)
                if 'USING_BOARD_CHAR_ID' in site_instance.info['EXTRA']:
                    bbs.board_char_id = item['id']
                else:
                    bbs.board_id = int(item['id'])
                bbs.title = item['title']
                bbs.url = item['url']
                bbs.magnet_count = len(item['magnet']) if item['magnet'] else 0
                bbs.file_count = len(item['download']) if item['download'] else 0
                bbs.magnet = '|'.join(item['magnet'])
                bbs.torrent_info = item['torrent_info'] if item['torrent_info'] else None
                if bbs.file_count > 0:
                    #bbs.files = '||'.join(u'%s|%s' % (x['link'], x['filename']) for x in item['download'])
                    bbs.files = '||'.join(u'%s|%s|%s' % (x['link'], x['filename'], x['direct_url'] if 'direct_url' in x else 'NONE') for x in item['download'])
                else:
                    bbs.files = None
                db.session.add(bbs)
                db.session.commit()
                ret.append(bbs)
            except Exception, e:
                logger.debug('Exception:%s', e)
                logger.debug(traceback.format_exc())
        return ret



    @staticmethod
    def __db_get_max_id(site_name, board):
        try:
            max_id = db.session.query(db.func.max(ModelBbs2.board_id)).filter_by(site=site_name, board=board).scalar()
            if type(max_id) == type(u''):
                max_id = int(max_id)
            return max_id
        except Exception, e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    

    

    
