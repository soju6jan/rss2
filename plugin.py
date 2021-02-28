# -*- coding: utf-8 -*-
#########################################################
# python
import os
import urllib
import traceback
import io
import json

# third-party
import requests
from flask import Blueprint, request, Response, send_file, render_template, redirect, jsonify, make_response
from flask_login import login_user, logout_user, current_user, login_required

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, check_api
from framework.util import Util

package_name = __name__.split('.')[0]
logger = get_logger(package_name)

# 패키지
#from .common import *
from .logic_from_site import LogicFromSite
from .logic import Logic
from .model import ModelSetting, ModelBbs2, ModelSite2, ModelScheduler2
from .logic_self import LogicSelf
from .logic_search_self import LogicSearchSelf
from system.model import ModelSetting as SystemModelSetting


blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
menu = {
    'main' : [package_name, u'RSS'],
    'sub' : [
        ['setting', u'설정'], ['site', u'지원 사이트'], ['scheduler', u'스케쥴링'], ['group', u'그룹화'], ['search', u'검색'], ['log', u'로그']
    ],
    'category' : 'torrent'
} 

def plugin_load():
    Logic.plugin_load()

def plugin_unload():
    Logic.plugin_unload()

plugin_info = {
    'version' : '0.1.0.0',
    'name' : u'RSS',
    'category_name' : 'torrent',
    'icon' : '',
    'developer' : 'soju6jan',
    'description' : u'토렌트 크롤링. 크롤링한 데이터, Bot으로 수신한 데이터 검색',
    'home' : 'https://github.com/soju6jan/rss2',
    'more' : '',
    #'policy_point' : 4000,
}
#########################################################


#########################################################
# WEB Menu   
#########################################################
@blueprint.route('/')
def home():
    return redirect('/%s/search' % package_name)

@blueprint.route('/<sub>')
@login_required
def first_menu(sub):
    try:
        if sub == 'setting':
            arg = ModelSetting.to_dict()
            arg['package_name']  = package_name
            arg['scheduler'] = str(scheduler.is_include(package_name))
            arg['is_running'] = str(scheduler.is_running(package_name))
            arg['is_test_server'] = (app.config['config']['is_server'] or app.config['config']['is_debug'])
            return render_template('%s_%s.html' % (package_name, sub), arg=arg)
        elif sub in ['site', 'scheduler', 'group']:
            arg = {'package_name' : package_name}
            return render_template('%s_%s.html' % (package_name, sub), arg=arg)
        elif sub == 'search':
            arg = {}
            arg = {'package_name' : package_name}
            arg['ddns'] = SystemModelSetting.get('ddns')
            
            try:
                import downloader
                arg['is_available_normal_download'] = downloader.Logic.is_available_normal_download()
            except:
                arg['is_available_normal_download'] = False
            arg["search_word"] = request.args.get('search_word')
            arg['is_torrent_info_installed'] = False
            try:
                import torrent_info
                arg['is_torrent_info_installed'] = True
            except Exception as e: 
                pass
            arg['apikey'] = ''
            if SystemModelSetting.get_bool('auth_use_apikey'):
                arg['apikey'] = SystemModelSetting.get('auth_apikey')
            
            return render_template('%s_%s.html' % (package_name, sub), arg=arg)
        elif sub == 'log':
            return render_template('log.html', package=package_name)
        return render_template('sample.html', title='%s - %s' % (package_name, sub))
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())




#########################################################
# For UI
#########################################################
@blueprint.route('/ajax/<sub>', methods=['GET', 'POST'])
@login_required
def ajax(sub):
    try:
        ret = {}
        # self - setting
        if sub == 'setting_save':
            ret = ModelSetting.setting_save(request)
            return jsonify(ret)
        elif sub == 'scheduler':
            go = request.form['scheduler']
            logger.debug('scheduler :%s', go)
            if go == 'true':
                Logic.scheduler_start()
            else:
                Logic.scheduler_stop()
            return jsonify(go)
        elif sub == 'one_execute':
            ret = Logic.one_execute()
            return jsonify(ret)
        elif sub == 'reset_db':
            ret = Logic.reset_db()
            return jsonify(ret)
        


        # self - site
        elif sub == 'load_site':
            ret['site'] = ModelSite2.get_list(by_dict=True)
            return jsonify(ret)
        elif sub == 'test':
            ret = LogicSelf.action_test(request)
            return jsonify(ret)
        elif sub == 'site_delete':
            ret['ret'] = ModelSite2.delete(request.form['site_id'])
            ret['site'] = ModelSite2.get_list(by_dict=True)
            return jsonify(ret)
        elif sub == 'site_edit':
            ret['ret'] = LogicSelf.site_edit(request)
            ret['site'] = ModelSite2.get_list(by_dict=True)
            return jsonify(ret)



        # self - scheduler
        elif sub == 'load_scheduler':
            ret['site'] = ModelSite2.get_list(by_dict=True)
            ret['scheduler'] = LogicSelf.get_scheduler_list()
            return jsonify(ret)
        elif sub == 'add_scheduler':
            ret['ret'] = LogicSelf.add_scheduler(request)            
            ret['site'] = ModelSite2.get_list(by_dict=True)
            ret['scheduler'] = LogicSelf.get_scheduler_list()
            return jsonify(ret)
        elif sub == 'remove_scheduler_db':
            ret['ret'] = LogicSelf.remove_scheduler_db_from_id(request.form['db_id']) 
            ret['site'] = ModelSite2.get_list(by_dict=True)
            ret['scheduler'] = LogicSelf.get_scheduler_list()
            return jsonify(ret)
        elif sub == 'remove_scheduler':
            ret['ret'] = LogicSelf.remove_scheduler(request)
            ret['site'] = ModelSite2.get_list(by_dict=True)
            ret['scheduler'] = LogicSelf.get_scheduler_list()
            return jsonify(ret)
 
        # self - group
        elif sub == 'load_group':
            ret['site'] = ModelSite2.get_list(by_dict=True)
            ret['group'] = LogicSelf.get_group_list()
            ret['info'] = LogicSelf.get_search_form_info()
            return jsonify(ret)
        elif sub == 'add_group':
            ret['ret'] = LogicSelf.add_group(request)          
            ret['site'] = ModelSite2.get_list(by_dict=True)
            ret['group'] = LogicSelf.get_group_list()
            ret['info'] = LogicSelf.get_search_form_info()
            return jsonify(ret)
        elif sub == 'remove_group':
            ret['ret'] = LogicSelf.remove_group(request)
            ret['site'] = ModelSite2.get_list(by_dict=True)       
            ret['group'] = LogicSelf.get_group_list()
            ret['info'] = LogicSelf.get_search_form_info()
            return jsonify(ret)
        elif sub == 'add_group_child':
            ret['ret'] = LogicSelf.add_group_child(request)          
            ret['site'] = ModelSite2.get_list(by_dict=True)
            ret['group'] = LogicSelf.get_group_list()
            ret['info'] = LogicSelf.get_search_form_info()
            return jsonify(ret)
        elif sub == 'remove_group_child':
            ret['ret'] = LogicSelf.remove_group_child(request)
            ret['site'] = ModelSite2.get_list(by_dict=True)   
            ret['group'] = LogicSelf.get_group_list()
            ret['info'] = LogicSelf.get_search_form_info()
            return jsonify(ret)



        # self - search
        elif sub == 'list':
            ret = LogicSearchSelf.get_list_by_web(request)
            return jsonify(ret)



        # 토렌트 인포
        elif sub == 'torrent_info':
            try:
                from torrent_info import Logic as TorrentInfoLogic
                data = request.form['hash']
                logger.debug(data)
                if data.startswith('magnet'):
                    ret = TorrentInfoLogic.parse_magnet_uri(data)
                else:
                    ret = TorrentInfoLogic.parse_torrent_url(data)
                return jsonify(ret)
            except Exception as e: 
                logger.error('Exception:%s', e)
                logger.error(traceback.format_exc())
        elif sub == 'server_test':
            logger.debug('server_test')
            """
            from sqlalchemy import desc
            from bot_downloader_movie.model import ModelMovieItem
            import json
            datas = db.session.query(ModelMovieItem).order_by(ModelMovieItem.id).limit(7000).all()
            for data in datas:
                response = requests.post("https://sjva.me/sjva/torrent_%s.php" % 'movie', data={'data':json.dumps(data.as_dict())})
            """
            group_name = 'AV'
            save_list = LogicSearchSelf.get_list(call='api', group=group_name)
            logger.debug(len(save_list))
            save_list = save_list[:10]
            if app.config['config']['is_server'] or app.config['config']['is_debug']:
                from tool_expand import TorrentProcess
                TorrentProcess.server_process(save_list, category=group_name)




            return ""

            #return jsonify(ret)
    
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())
        return jsonify('fail')




#########################################################
# API - 자막파일
#########################################################

@blueprint.route('/api/download/<bbs_id>', methods=['GET'])
@check_api
def api_download(bbs_id):
    logger.debug('api download :%s', bbs_id)
    try :
        rss_id, index = bbs_id.split('_')

        entity = ModelBbs2.get(id=int(rss_id)).as_dict()

        #logger.debug(entity)
        scheduler_instance = ModelScheduler2.get2(sitename=entity['site'], board_id=entity['board'])
        data = [
            entity['url'],
            entity['files'][int(index)][0],
            entity['files'][int(index)][1]
        ]
        
        site_instance = ModelSite2.get(name=entity['site']).info

        if 'USE_SELENIUM' in site_instance['EXTRA']:
            from system import SystemLogicSelenium
            driver = SystemLogicSelenium.get_driver()

            SystemLogicSelenium.get_pagesoruce_by_selenium(data[0], site_instance['SELENIUM_WAIT_TAG'])

            logger.debug(data[1])
            logger.debug('selenium download go..')
            driver.get(data[1])
            logger.debug('selenium wait before...')
            #SystemLogicSelenium.waitUntilDownloadCompleted(120)
            #SystemLogicSelenium.waitUntilDownloadCompleted(10)
            import time
            time.sleep(10)
            logger.debug('selenium wait end')
            files = SystemLogicSelenium.get_downloaded_files()
            logger.debug(files)
            # 파일확인
            filename_no_ext = os.path.splitext(data[2].split('/')[-1])
            file_index = 0
            for idx, value in enumerate(files):
                if value.find(filename_no_ext[0]) != -1:
                    file_index =  idx
                    break
            logger.debug('fileindex : %s', file_index)
            content = SystemLogicSelenium.get_file_content(files[file_index])
            byteio = io.BytesIO()
            byteio.write(content)
            filedata = byteio.getvalue()
            return send_file(
                io.BytesIO(filedata),
                mimetype='application/octet-stream',
                as_attachment=True,
                attachment_filename=data[2])
       
        return download2(data, scheduler_instance)
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

def download2(data, scheduler_instance):
    logger.debug(data)
    try:
        LogicFromSite.set_proxy(scheduler_instance)
        page = LogicFromSite.get_html(data[0])
        page = LogicFromSite.get_html(data[1], referer=data[0], stream=True)
        
        byteio = io.BytesIO()
        for chunk in page.iter_content(1024):
            byteio.write(chunk)

        filedata = byteio.getvalue()
        logger.debug('LENGTH : %s', len(filedata))
        
        logger.debug('filename : %s', data[2])
        return send_file(
            io.BytesIO(filedata),
            mimetype='application/octet-stream',
            as_attachment=True,
            attachment_filename=data[2])
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

#########################################################

#########################################################
# API - sjva.me 연동
#########################################################
@blueprint.route('/api/<sub>', methods=['GET', 'POST'])
@check_api
def api_web(sub):
    try :
        if sub == 'site_update':
            content = request.form['content']
            import base64
            decode_content = base64.b64decode(content).decode('utf8')
            #logger.debug(decode_content)
            #decode_content = content
            info = LogicSelf.parse_site_info_from_string(decode_content)
            #logger.debug(info)
            ret = {}
            if info is None:
                ret['ret'] = 'error'
                ret['log'] = '변환에 실패하였습니다.'
            else:
                ret = ModelSite2.save('web', info, decode_content)
            #logger.debug(ret)
            return jsonify(ret)
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())
#########################################################




#########################################################
# API - 외부
#########################################################
@blueprint.route('/api/board/<sitename>/<boardname>')
@check_api
def api_rss(sitename, boardname):
    try:
        xml = LogicSearchSelf.get_list_by_api(request, True, -1, sitename, boardname)
        return Response(xml, mimetype='application/xml')
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

@blueprint.route('/api/board_id/<id>')
@check_api
def api_board_id(id):
    try:
        tmp = db.session.query(ModelScheduler2).filter_by(id=id).first()
        if tmp is not None:
            xml = LogicSearchSelf.get_list_by_api(request, True, -1, tmp.sitename, tmp.board_id)
            return Response(xml, mimetype='application/xml')
        else:
            return jsonify('not exist')
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

@blueprint.route('/api/group/<name>')
@check_api
def api_group(name):
    try:
        xml = LogicSearchSelf.get_list_by_api(request, False, name)
        return Response(xml, mimetype='application/xml')
    except Exception as e:
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

    

