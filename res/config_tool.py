from configparser import ConfigParser
from cryptography.fernet import Fernet
import datetime
import os

import res_temp
from res import app_logger
logger = app_logger.get_logger(__name__)

CONFIG_FOLDER = os.path.join(os.getcwd(), 'res', 'conf')
BASE_CONF = 'base.conf'


class ConfigTool:
    def __init__(self, engine=None):
        self.engine = engine
        self.base_config = ConfigParser()
        self.config = ConfigParser()

        self.base_path = os.path.join(CONFIG_FOLDER, BASE_CONF)
        try:
            self.base_config.read(self.base_path)
        except:
            logger.exception('Base config file error: ')

        self.path = os.path.join(CONFIG_FOLDER, self.get_main_conf())
        try:
            self.config.read(self.path)
        except:
            logger.exception('Config file error: ')

        self.active_pid = self.get_active_pid_file()
        self.pid_config = ConfigParser()

    def save_config(self, table):
        for section in table.keys():
            self.config.add_section(section)
            for option in table[section].keys():
                if option == "password":
                    password = self.__save_password(table[section][option])
                    self.config.set(section, option, password)
                else:
                    self.config.set(section, option, table[section][option])

        with open(self.path, 'w') as config_file:
            self.config.write(config_file)

    def add_active_pid(self, task_id, pid):
        self.pid_config.add_section('DEFAULT')
        self.pid_config.set('DEFAULT', task_id, pid)

        with open(self.active_pid, 'w') as f:
            self.pid_config.write(f)

    def get_active_pid(self):
        pid_dict = dict()
        try:
            self.pid_config.read(self.active_pid)
        except:
            logger.exception('Active pid read: ')
            return pid_dict
        pid_list = self.pid_config.defaults()
        for line in pid_list:
            pid_dict[line[0]] = line[1]
        return pid_dict

    def get_main_conf(self):
        return self.base_config.get('base', 'main_conf')

    def get_tmp(self):
        return os.path.join(os.getcwd(), self.base_config.get('base', 'tmp'))

    def get_pid_folder(self):
        return self.base_config.get('base', 'pid_folder')

    def get_active_pid_file(self):
        return os.path.join(self.get_tmp(), self.base_config.get('base', 'active_pid'))

    @staticmethod
    def get_time():
        return datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    def get_engines(self):
        return self.config.sections()

    def get_url(self):
        url = 'https://' + self.config.get(self.engine, 'url') + '/ovirt-engine/api'
        return url

    def get_username(self):
        return self.config.get(self.engine, 'username')

    def get_password(self):
        password = self.__load_password(self.config.get(self.engine, 'password'))
        if password:
            return password
        else:
            return ''

    def get_ca_file(self):
        return os.path.join(CONFIG_FOLDER, self.config.get(self.engine, 'ca_file'))

    def get_backup_server(self):
        return self.config.get(self.engine, 'backup_server')

    def get_backup_dir(self):
        return self.config.get(self.engine, 'main_backup_dir')

    def get_snapshot_description(self):
        return self.config.get(self.engine, 'snapshot_description').format(self.get_time())

    def get_snapshot_timeout(self):
        return int(self.config.get(self.engine, 'snapshot_timeout'))

    def get_disk_finding_timeout(self):
        return int(self.config.get(self.engine, 'disk_finding_timeout'))

    def get_remote_server(self):
        return bool(int(self.config.get(self.engine, 'remote_server')))

    def get_remote_fqdn(self):
        return self.config.get(self.engine, 'remote_fqdn')

    def get_remote_user(self):
        return self.config.get(self.engine, 'remote_user')

    @staticmethod
    def __save_password(password):
        """encrypt_password = Fernet(res_temp.KEY).encrypt(table[section][option].encode('utf-8'))
                            config.set(section, option, encrypt_password.decode('utf-8'))"""
        try:
            encrypt_password = Fernet(res_temp.KEY).encrypt(password.encode('utf-8'))
        except:
            logger.exception('saving password error: ')
            return 'saving_err'
        else:
            logger.info('saving password success')
            return encrypt_password.decode('utf-8')

    @staticmethod
    def __load_password(encrypt_password):
        try:
            decrypt_password = Fernet(res_temp.KEY).decrypt(encrypt_password.encode('utf-8'))
        except:
            logger.exception('load password error: ')
        else:
            return decrypt_password.decode('utf-8')


if __name__ == '__main__':
    conf = ConfigTool('ovirthe_rep')
    conf.save_config(res_temp.CONFIG_TABLE)
    # print(conf.get_password())
