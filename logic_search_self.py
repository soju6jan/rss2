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
from system.model import ModelSetting as SystemModelSetting

# 패키지
from .plugin import logger, package_name
from .logic_from_site import LogicFromSite
from .model import ModelSetting, ModelScheduler2, ModelBbs2,  ModelGroup2
import telegram_bot
from .logic_self import LogicSelf

#########################################################

class LogicSearchSelf(object):
    @staticmethod
    def get_list_by_web(req):
        ret = {}        
        load = req.form['load'] if 'load' in req.form else 'false'
        if load == 'true':
            ret['info'] = LogicSelf.get_search_form_info()
            search_word = req.form['search_word']
            if search_word is not None and search_word != 'None':
                lists, paging = LogicSearchSelf.get_list(search_word=search_word)
            else:
                lists, paging = LogicSearchSelf.get_list()
        else:        
        #radio=site&site_select=all&board_select=all&group_select=all&search_select=title&search_word=&site_radio=true&page=7
            site_select = req.form['site_select'] if 'site_select' in req.form and req.form['site_select'] != 'all' else None
            board_select = req.form['board_select'] if 'board_select' in req.form and req.form['board_select'] != 'all' else None
            group_select = req.form['group_select'] if 'group_select' in req.form and req.form['group_select'] != 'all' else None
            search_select = req.form['search_select']
            search_word = req.form['search_word']
            site_radio = req.form['site_radio']
            page = int(req.form['page']) if req.form['page'] is not None else 1

            if site_radio == 'true':
                lists, paging = LogicSearchSelf.get_list(sitename=site_select, board=board_select, page=page, select_column= search_select, search_word=search_word)
            else:
                lists, paging = LogicSearchSelf.get_list(group=group_select, page=page, select_column= search_select, search_word=search_word)

        
        ret['list'] = [item.as_dict() for item in lists]
        ret['paging'] = paging
        return ret        

        #radio=site&site_select=all&board_select=all&search_select=title&search_word=&site_radio=true&page=1
    # call : web, api

    @staticmethod
    def get_list(call='web', group=None, sitename=None, board=None, page=1, select_column=None, search_word=None):
        try:
            if call == 'web':
                page_size = ModelSetting.get_int('web_page_size')
            else:
                page_size = ModelSetting.get_int('feed_count')
            

            query = db.session.query(ModelBbs2)#.join(ModelFile2)
            
            # 그룹만 있고, 게시판 등록을 안할 경우 검색 안되도록
            add_group_query = False
            if group is not None and group != '':
                conditions = []
                group_entity = db.session.query(ModelGroup2).filter_by(groupname=group).first()
                if group_entity is not None:
                    #2019-05-18
                    add_group_query = (len(group_entity.schedulers) > 1)
                    if len(group_entity.schedulers) == 0:
                        query = query.filter(ModelBbs2.site == 'not_child')
                    elif len(group_entity.schedulers) == 1:
                        query = query.filter(ModelBbs2.site == group_entity.schedulers[0].sitename)
                        query = query.filter(ModelBbs2.board == group_entity.schedulers[0].board_id)
                    else:
                        for item in group_entity.schedulers:
                            conditions.append( and_(ModelBbs2.site == item.sitename, ModelBbs2.board == item.board_id))
                        query = query.filter(or_(*conditions))
            else:
                if sitename is not None and sitename != '':
                    query = query.filter(ModelBbs2.site == sitename)
                if board is not None and board != '':
                    query = query.filter(ModelBbs2.board == board)
            if search_word is not None and search_word != '':
                if select_column is None or select_column == 'title':
                    if search_word.find('|') != -1:
                        tmp = search_word.split('|')
                        conditions = []
                        for tt in tmp:
                            if tt != '':
                                conditions.append( ModelBbs2.title.like('%'+tt.strip()+'%') )
                        query = query.filter(or_(*conditions))
                    elif search_word.find(',') != -1:
                        tmp = search_word.split(',')
                        for tt in tmp:
                            if tt != '':
                                query = query.filter(ModelBbs2.title.like('%'+tt.strip()+'%'))
                    else:
                        
                        if ModelBbs2.torrent_info is None:
                            query = query.filter(ModelBbs2.title.like('%'+search_word.strip()+'%'))
                        else:
                            conditions = []
                            conditions.append( ModelBbs2.title.like('%'+search_word.strip()+'%') )   
                            conditions.append( ModelBbs2.torrent_info.like('%'+search_word.strip()+'%') )
                            query = query.filter(or_(*conditions))

                    #query = query.filter(ModelBbs.title.like('%'+search_word+'%'))
                elif select_column == 'filename':
                    #query = query.filter(ModelBbs.files.any(ModelFile.filename.like('%'+search_word+'%')))
                    query = query.filter(ModelFile.filename.like('%'+search_word+'%'))
                elif select_column == 'magnet':
                    #query = query.filter(ModelBbs.files.any(ModelFile.magnet.like('%'+search_word+'%')))
                    
                    query = query.filter(ModelFile.magnet.like('%'+search_word+'%'))
                else:
                    query = query.filter(ModelBbs2.title.like('%'+search_word+'%'))

            
            if group is not None and group != '' and add_group_query:
                #query = query.with_entities(ModelBbs.magnet).distinct()
                #query = query.distinct(ModelBbs.files.magnet)
                
                subq = (db.session.query(func.min(ModelBbs2.id).label("min_id"))
                        .group_by(ModelBbs2.magnet).filter(or_(*conditions))).subquery()
                query = query.join(subq, and_(ModelBbs2.id == subq.c.min_id))
                query = query

            #logger.debug('GET LIST: %s', query)
            count = query.count()
            query = (query.order_by(desc(ModelBbs2.id))
                        .limit(page_size)
                        .offset((page-1)*page_size)
                )
            ret = query.all()
            #logger.debug('LAST QUERY : %s', query)
            if call == 'api':
                return ret
            #return Util.db_to_dict(query)
            paging = Util.get_paging_info(count, page, page_size)
            return ret, paging
          
        except Exception, e:
            logger.debug('Exception:%s', e)
            logger.debug(traceback.format_exc())


    #########################################################
    # RSS API
    #########################################################
    @staticmethod
    def get_list_by_api(req, is_site, arg, site=None, board_id=None):
        try:
            #default_torrent_mode = db.session.query(ModelSetting).filter_by(key='default_torrent_mode').first().value
            default_torrent_mode = 'magnet'
            torrent_mode = req.args.get('torrent_mode')
            search_word = req.args.get('search')
            if search_word is not None and search_word != '':
                search_word = search_word.replace(' ', '+')
            if torrent_mode is not None:
                default_torrent_mode = torrent_mode
            
            if is_site:
                if site is None:
                    sched_entity = db.session.query(ModelScheduler2).filter_by(id=arg).first()
                else:
                    sched_entity = db.session.query(ModelScheduler2).filter_by(sitename=site).filter_by(board_id=board_id).first()

                items = LogicSearchSelf.get_list(call='api', sitename=sched_entity.sitename, board=sched_entity.board_id, search_word=search_word)
                title = 'SITE : %s  BOARD : %s' % (sched_entity.sitename, sched_entity.board_id)
            else:
                groupname = arg
                group_entity = db.session.query(ModelGroup2).filter_by(groupname=arg).first()
                items = LogicSearchSelf.get_list(call='api', group=group_entity.groupname, search_word=search_word)
                title = 'GROUP : %s' % (group_entity.groupname)

            #from .torrent_site_base import TorrentSite
            
            xml = LogicSearchSelf.make_rss(title, items, default_torrent_mode, SystemLogic.get_setting_value('ddns'))
                
            
            return xml   
        except Exception, e:
            logger.debug('Exception:%s', e)
            logger.debug(traceback.format_exc())
            logger.debug('get_list_by_api is_site:%s, arg:%s, site:%s, board_id:%s', is_site, arg, site, board_id)



    @staticmethod
    def make_rss(title, rss_list, torrent_mode, ddns, is_bot=False, search_word=None):
        from framework.common.rss import RssUtil
        xml = '<rss xmlns:showrss="http://showrss.info/" version="2.0">\n'
        xml += '\t<channel>\n'
        xml += '\t\t<title>' + '%s</title>\n' % title
        xml += '\t\t<link></link>\n'
        xml += '\t\t<description></description>\n'
        magnet_flag = False
        for bbs in rss_list:
            _dict = bbs.as_dict()
            if bbs.torrent_info is None and 'magnet' in _dict and _dict['magnet'] is not None:
                for magnet in _dict['magnet']:
                    magnet_flag = True
                    item_str = '\t\t<item>\n'
                    tmp = '\t\t\t<title>%s</title>\n' % RssUtil.replace_xml(bbs.title)
                    item_str += tmp
                    item_str += '\t\t\t<link>%s</link>\n' % magnet
                    date_str = bbs.created_time.strftime('%a, %d %b %Y %H:%M:%S') + ' +0900'
                    item_str += '\t\t\t<pubDate>%s</pubDate>\n' % date_str
                    item_str += '\t\t</item>\n'
                    xml += item_str

            else:
                if bbs.torrent_info is not None:
                    for info in bbs.torrent_info:
                        magnet_flag = True
                        item_str = '\t\t<item>\n'
                        if search_word is not None and search_word != '' and info['name'].find(search_word) == -1:
                            continue
                        tmp = '\t\t\t<title>%s</title>\n' % RssUtil.replace_xml(info['name'])
                        item_str += tmp
                        item_str += '\t\t\t<link>magnet:?xt=urn:btih:%s</link>\n' % info['info_hash']
                        date_str = bbs.created_time.strftime('%a, %d %b %Y %H:%M:%S') + ' +0900'
                        item_str += '\t\t\t<pubDate>%s</pubDate>\n' % date_str
                        item_str += '\t\t</item>\n'
                        xml += item_str

            if _dict['files']:
                for index, download in enumerate(_dict['files']):
                    try:
                        item_str = '\t\t<item>\n'
                        if magnet_flag and download[1].lower().endswith('.torrent'):
                            continue
                        item_str += '\t\t\t<title>%s</title>\n' % RssUtil.replace_xml(download[1])
                        url = '%s/%s/api/download/%s_%s' % (ddns, package_name, bbs.id, index)
                        if SystemModelSetting.get_bool('auth_use_apikey'):
                            url += '?apikey=%s' % SystemModelSetting.get('auth_apikey')
                        item_str += '\t\t\t<link>%s</link>\n' % url
                        date_str = bbs.created_time.strftime('%a, %d %b %Y %H:%M:%S') + ' +0900'
                        item_str += '\t\t\t<pubDate>%s</pubDate>\n' % date_str
                        item_str += '\t\t</item>\n'
                        xml += item_str
                    except Exception as e:
                        logger.debug('Exception:%s', e)
                        logger.debug(traceback.format_exc())

        xml += '\t</channel>\n'
        xml += '</rss>'
        return xml
