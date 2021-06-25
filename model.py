# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import json
from datetime import datetime

# third-party
from sqlalchemy.orm.attributes import flag_modified

# sjva 공용
from framework import db, app, path_app_root

# 패키지
from .plugin import logger, package_name

app.config['SQLALCHEMY_BINDS'][package_name] = 'sqlite:///%s' % (os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name))

class ModelSetting(db.Model):
    __tablename__ = '%s_setting' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)
 
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        return {x.name: getattr(self, x.name) for x in self.__table__.columns}

    @staticmethod
    def get(key):
        try:
            return db.session.query(ModelSetting).filter_by(key=key).first().value.strip()
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
            
    
    @staticmethod
    def get_int(key):
        try:
            return int(ModelSetting.get(key))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def get_bool(key):
        try:
            return (ModelSetting.get(key) == 'True')
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def set(key, value):
        try:
            item = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
            if item is not None:
                item.value = value.strip()
                db.session.commit()
            else:
                db.session.add(ModelSetting(key, value.strip()))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def to_dict():
        try:
            from framework.util import Util
            return Util.db_list_to_dict(db.session.query(ModelSetting).all())
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())


    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                if key in ['scheduler', 'is_running']:
                    continue
                logger.debug('Key:%s Value:%s', key, value)
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True                  
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            logger.debug('Error Key:%s Value:%s', key, value)
            return False

#########################################################


class ModelSite2(db.Model):
    __tablename__ = '%s_site' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)
    

    info_type = db.Column(db.String)
    name = db.Column(db.String)
    info = db.Column(db.JSON)
    content = db.Column(db.String)
    schedulers = db.relationship('ModelScheduler2', backref='site', lazy=True)

    def __init__(self, info_type, info, content):
        self.created_time = datetime.now()
        self.info_type = info_type
        self.name = info['NAME']
        self.info = info
        self.content = content

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S')
        return ret


    @staticmethod
    def save(info_type, info, content):
        try:
            ret = {}
            if 'NAME' in info:
                name = info['NAME']
            entity = db.session.query(ModelSite2).filter_by(name=name, info=info, content=content).first()
            if entity is not None:
                ret['ret'] = "already_save"
                ret['log'] = "이미 저장되어 있습니다."
            else:
                entity = db.session.query(ModelSite2).filter_by(name=name).with_for_update().first()
                if entity is not None:
                    entity.info = info
                    entity.content = content
                    entity.info_type = info_type
                    flag_modified(entity, "info")
                    db.session.commit()
                    ret['ret'] = "update"
                    ret['log'] = "업데이트하였습니다."
                else:
                    entity = ModelSite2(info_type, info, content)
                    db.session.add(entity)
                    db.session.commit()
                    ret['ret'] = "add"
                    ret['log'] = "추가하였습니다."
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret['ret'] = "exception"
            ret['log'] = "DB 저장에 실패하였습니다."
        try:
            count = db.session.query(ModelSite2).filter_by(info_type='web').count()
            ret['log'] += '<br>' + '총 %s개의 웹 연동 정보가 있습니다.' % (count)
            return ret
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    # 전체 사이트 목록
    @staticmethod
    def get_list(by_dict=False):
        try:
            tmp = db.session.query(ModelSite2).all()
            if by_dict:
                tmp = [x.as_dict() for x in tmp]
            return tmp
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get(site_id=None, name=None, by_dict=False):
        try:
            query = db.session.query(ModelSite2)
            if site_id is not None:
                if type(site_id) != type(1):
                    site_id = int(site_id)
                query = query.filter_by(id=site_id)
            if name is not None:
                query = query.filter_by(name=name)
            tmp = query.first()
            if by_dict:
                return tmp.as_dict()
            else:
                return tmp
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @staticmethod
    def delete(site_id):
        try:
            site = db.session.query(ModelSite2).filter_by(id=site_id).first()
            db.session.query(ModelBbs2).filter_by(site=site.name).delete()
            db.session.query(ModelScheduler2).filter_by(site_id=site.id).delete()
            db.session.query(ModelSite2).filter_by(id=site_id).delete()
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
            


class ModelScheduler2(db.Model):
    __tablename__ = '%s_scheduler2' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)
    
    site_id = db.Column(db.Integer, db.ForeignKey('%s_site.id' % package_name))
    sitename = db.Column(db.String)
    board_id = db.Column(db.String)
    include_scheduler = db.Column(db.Boolean)
    use_proxy = db.Column(db.Boolean)
    use_torrent_info = db.Column(db.Boolean)
    
    group_id= db.Column(db.Integer, db.ForeignKey('%s_group.id' % package_name))
    bbs = db.relationship('ModelBbs2', backref='scheduler', lazy=True)

    # 2버전추가
    priority = db.Column(db.Integer)
    scheduler_interval = db.Column(db.Integer) # 스케쥴러 몇회마다 한번씩 수행할지 결정할 값 0:매번수행, 1: 실행-실행 2: 실행-패스-실행 , 3:실행-패스-패스-실행
    #scheduler_interval_current = db.Column(db.Integer) # 

    def __init__(self, site_instance):
        self.created_time = datetime.now()
        self.site_id = site_instance.id
        self.sitename = site_instance.name


    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S')
        return ret

    @staticmethod
    def get_list(by_dict=False):
        try:
            query = db.session.query(ModelScheduler2)
            query = query.order_by(ModelScheduler2.priority)
            query = query.order_by(ModelScheduler2.id)
            tmp = query.all()
            if by_dict:
                tmp = [x.as_dict() for x in tmp]
            return tmp
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get(site_id, board_id, by_dict=False):
        try:
            site_id = int(site_id)
            tmp = db.session.query(ModelScheduler2).filter_by(site_id=site_id).filter_by(board_id=board_id).first()
            if by_dict:
                return tmp.as_dict()
            else:
                return tmp
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get2(sitename=None, board_id=None, by_dict=False):
        try:
            tmp = db.session.query(ModelScheduler2).filter_by(sitename=sitename).filter_by(board_id=board_id).first()
            if by_dict:
                return tmp.as_dict()
            else:
                return tmp
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    def get_last_bbs(self):
        try:
            if 'USING_BOARD_CHAR_ID' not in self.site.info['EXTRA']:
                max_id = db.session.query(db.func.max(ModelBbs2.board_id)).filter_by(site=self.sitename, board=self.board_id).scalar()
                if max_id > 0:
                    return db.session.query(ModelBbs2).filter_by(site=self.sitename, board=self.board_id, board_id=max_id).first()
            else:
                if self.bbs:
                    return self.bbs[-1]
                return None
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    

class ModelBbs2(db.Model):
    __tablename__ = '%s_bbs2' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    site = db.Column(db.String)
    board = db.Column(db.String)  # 게시판 이름. 
    board_id = db.Column(db.Integer)  # 게시판에서의 ID
    board_char_id = db.Column(db.String)
    title = db.Column(db.String)
    url = db.Column(db.String)
    magnet_count = db.Column(db.Integer)
    file_count = db.Column(db.Integer)
    magnet = db.Column(db.String) #구분자 |
    files = db.Column(db.String)  # url|filename||url|filename
    torrent_info = db.Column(db.JSON)
    scheduler_id = db.Column(db.Integer, db.ForeignKey('%s_scheduler2.id' % package_name))
    broadcast_status = db.Column(db.String)
   

    def __init__(self, scheduler_instance):
        self.scheduler = scheduler_instance
        self.created_time = datetime.now()
        self.files = None
        self.torrent_info = None
        self.site = scheduler_instance.site.info['NAME']
        self.board = scheduler_instance.board_id
        self.broadcast_status = ''

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%m-%d %H:%M:%S')
        if ret['magnet'] is not None:
            ret['magnet'] = self.magnet.split('|')
            if len(ret['magnet']) == 1 and ret['magnet'][0] == '':
                ret['magnet'] = None
        if ret['files'] is not None:
            tmp = self.files.split('||')
            ret['files'] = []
            for t in tmp:
                if t == '':
                    continue
                ret['files'].append(t.split('|'))
        return ret
    
    @staticmethod
    def get(id=None, site=None, board=None, board_id=None, board_char_id=None):
        try:
            #entity = db.session.query(ModelBbs2).filter_by(id=id).first()
            query = db.session.query(ModelBbs2)
            if id is not None:
                query = query.filter_by(id=id)
            if site is not None:
                query = query.filter_by(site=site)
            if board is not None:
                query = query.filter_by(board=board)
            if board_id is not None:
                query = query.filter_by(board_id=board_id)
            if board_char_id is not None:
                query = query.filter_by(board_char_id=board_char_id)
            entity = query.first()
            return entity
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())



class ModelGroup2(db.Model):
    __tablename__ = '%s_group' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time = db.Column(db.DateTime)
    reserved = db.Column(db.JSON)

    groupname = db.Column(db.String())
    #schedulers = db.relationship('ModelScheduler2', backref='plugin_%s_scheduler2' % package_name, lazy=True)
    schedulers = db.relationship('ModelScheduler2', backref='groups', lazy=True)
    query = db.Column(db.String())

    #schedulers = db.relationship('ModelScheduler2', secondary=group_scheduler2, backref=db.backref('ModelGroup2'))

    def __init__(self):
        self.created_time = datetime.now()

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['schedulers'] = []
        for f in self.schedulers:
            ret['schedulers'].append(f.as_dict())
        return ret

    @staticmethod
    def get_list(by_dict=False):
        try:
            tmp = db.session.query(ModelGroup2).all()
            if by_dict:
                tmp = [x.as_dict() for x in tmp]
            return tmp
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())











