import os

import config_tool
import app_logger
logger = app_logger.get_logger(__name__)


class Status:
    def __init__(self):
        self.config = config_tool.ConfigTool()
        self.tmp = self.config.get_tmp()
        self.active_pid = self.config.get_active_pid_file()
        self.info_file = ''
        self.info = dict()

    def get(self):
        status = dict()
        tasks = self.config.get_active_pid()
        if not tasks:
            return
        for task_id in tasks.keys():
            info_file = os.path.join(self.tmp, task_id + '.info')
            try:
                with open(info_file, 'r') as f:
                    info = f.read()
            except:
                logger.exception('Get info file: ')
                info = ''
            data_file = os.path.join(self.tmp, task_id + '.dat')
            try:
                with open(data_file, 'r') as f:
                    data = int(f.readlines()[-1])
            except:
                logger.exception('Get info file: ')
                data = 0
            status[task_id] = {
                'info': info,
                'data': data,
            }
        return status

    def status_file(self, task_id):
        self.info_file = os.path.join(self.tmp, task_id + '.info')

    def send_info(self, data):
        with open(self.info_file, 'a') as f:
            f.write(data)
