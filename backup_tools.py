import os
import time
import glob
import json
import subprocess
import ovirtsdk4 as sdk
from ovirtsdk4 import types

from res import app_logger, config_tool
from res import utils
from res import status
logger = app_logger.get_logger(__name__)


class Api:
    def __init__(self, settings, task_id):
        self.task_id = task_id
        self.settings = settings
        self.config = config_tool.ConfigTool(self.settings['engine'])
        self.url = self.config.get_url()
        self.username = self.config.get_username()
        self.password = self.config.get_password()
        self.ca_file = self.config.get_ca_file()
        self.main_backup_dir = self.config.get_backup_dir()
        self.tmp = self.config.get_tmp()
        self.status = status.Status()
        self.status.info_file(task_id)

        self.api_service = None
        self.vms_service = None
        self.backup_vm_service = None
        self.vm_service = None

        self.vm_backup_dir = ''
        self.vm_settings = dict()
        self.task_settings = dict()
        self.disks_meta = dict()

    def __enter__(self):
        self.__get_api_service()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__api_close()

    def __get_api_service(self):
        logger.info('Connect to ovirt')
        try:
            self.api = sdk.Connection(
                url=self.url,
                username=self.username,
                password=self.password,
                ca_file=self.ca_file,
                # insecure=True,
                # debug=True,
            )
        except sdk.Error:
            logger.exception('Connection error: ')
        except:
            logger.exception('Unexpected Connection error: ')
        else:
            self.api_service = self.api.system_service()
            self.vms_service = self.api_service.vms_service()
            self.backup_vm_service = self.__get_vm_service(self.config.get_backup_server())

    def __api_close(self):
        self.api.close()

    def get_vm_id(self, vm_name):
        vm = self.vms_service.list(search=f'name={vm_name}')
        try:
            return vm[0].id
        except IndexError:
            logger.exception(f'Can`t get vm {vm_name}')

    def __get_vm_service(self, vm_name):
        vm_id = self.get_vm_id(vm_name)
        try:
            return self.vms_service.vm_service(vm_id)
        except:
            logger.exception('Get vm service error: ')

    def __find_disk(self, attachment):
        timeout = self.config.get_disk_finding_timeout()
        pause = 5
        tries = timeout // pause

        for i in range(tries):
            logger.info('Searching for image')
            for path in glob.glob('/sys/block/*/serial'):
                with open(path, 'r') as f:
                    serial = f.read()
                if serial == attachment.disk.id[:20]:
                    disk_name = path.split('/')[3]
                    return f'/dev/{disk_name}'
            time.sleep(pause)
        logger.error('Cannot find attached disk')

    def __get_cluster_name(self, cluster_id):
        clusters_service = self.api_service.clusters_service()
        for cluster in clusters_service.list():
            if cluster_id == cluster.id:
                return cluster.name

    def __get_nic_profile_name(self, nic_id):
        nic_service = self.api_service.vnic_profiles_service()
        for nic in nic_service.list():
            if nic_id == nic.id:
                return nic.name

    def __get_nic_profile_id(self, nic_name):
        nic_service = self.api_service.vnic_profiles_service()
        for nic in nic_service.list():
            if nic_name == nic.name:
                return nic.id

    def __get_shell_command(self, input_file, output_file, progress):
        compress_types = utils.COMPRESS_TYPES
        compress = self.task_settings['compress']
        cmd_ssh = []
        if self.settings['task'] == 'backup':
            output_file += compress_types[compress][0]
            cmd_compress = ['|'] + compress_types[compress][1]
        elif self.settings['task'] == 'restore':
            input_file += compress_types[compress][0]
            cmd_compress = ['|'] + compress_types[compress][2]
        else:
            logger.error('get_backup_command error')
            return
        if self.config.get_remote_server():
            cmd_ssh = ['ssh', self.config.get_remote_user() + '@' + self.config.get_remote_fqdn()]
        cmd_pv = ['pv', '-n', input_file]
        cmd_dd = ['|', 'dd', 'bs=1M', 'conv=notrunc,noerror', 'status=none', 'of=' + output_file]
        cmd_progress = ['>', progress, '2>&1']

        cmd = cmd_ssh + ['('] + cmd_pv + cmd_compress + cmd_dd + [')'] + cmd_progress
        return cmd


class Backup(Api):
    def __init__(self, settings, task_id):
        super(Backup, self).__init__(settings, task_id)

        self.snapshots_service = None
        self.snapshot = None

    def run(self):
        logger.info('Start backup (task id=' + self.task_id + ')')
        self.status.send_info('Start backup')
        self.task_settings = self.settings['backup']
        backup_name = self.task_settings['backup_name']
        backup_dir = os.path.join(self.main_backup_dir, backup_name)
        if not os.path.isdir(backup_dir):
            os.makedirs(backup_dir)
        vms = self.task_settings['vms']

        for vm_name, disks in vms.items():
            self.vm_service = self.__get_vm_service(vm_name)

            vm_dir = os.path.join(backup_dir, vm_name)
            if not os.path.isdir(vm_dir):
                os.makedirs(vm_dir)
            task_time = self.config.get_time()
            self.vm_backup_dir = os.path.join(vm_dir, task_time)
            os.makedirs(self.vm_backup_dir)

            self.__save_vm_settings(self.vm_service.get(all_content=True), vm_name)
            self.__meta_create()

            self.snapshots_service = self.vm_service.snapshots_service()
            self.snapshot = self.snapshots_service.add(
                snapshot=types.Snapshot(
                    description=self.config.get_snapshot_description(),
                    persist_memorystate=False
                )
            )
            self.__waiting_for_snapshot_creation()
            self.__backup_images()
        self.__api_close()

    def __waiting_for_snapshot_creation(self):
        self.snapshot_service = self.snapshots_service.snapshot_service(self.snapshot.id)
        snapshot_status = types.SnapshotStatus.LOCKED

        timeout = self.config.get_snapshot_timeout()
        pause = 2
        tries = timeout // pause

        logger.info('Start snapshot creating...')
        for i in range(tries):
            try:
                snapshot_status = self.snapshot_service.get().snapshot_status
            except:
                logger.exception('Error getting snapshot status: ')
            if snapshot_status == types.SnapshotStatus.OK:
                break
            logger.debug(f'Snapshot {self.snapshot.id} creation in progress...')
            time.sleep(pause)
        else:
            logger.error('Timeout snapshot creating!')

    def __backup_images(self):
        disks_service = self.snapshot_service.disks_service()
        attachments_service = self.backup_vm_service.disk_attachments_service()

        for disk in disks_service.list():
            disk_meta = self.disks_meta[disk.id]
            disk_meta['compress'] = self.task_settings['compress']

            attachment = attachments_service.add(
                attachment=types.DiskAttachment(
                    disk=types.Disk(
                        id=disk.id,
                        snapshot=types.Snapshot(id=self.snapshot.id)
                    ),
                    active=True,
                    bootable=False,
                    interface=utils.DISK_INTERFACE[disk_meta['interface']],
                )
            )
            attachment_service = attachments_service.attachment_service(attachment.id)
            disk_image = self.__find_disk(attachment)
            self.__save_disk(disk_image, disk_meta)
            attachment_service.remove(wait=True)

    def __save_disk(self, disk_image, disk_meta):
        output_file = os.path.join(self.vm_backup_dir, disk_meta['alias'] + '_' + disk_meta['id'])
        meta_file = output_file + '.meta'
        progress = os.path.join(self.tmp, self.task_id + '.dat')
        cmd_save = self.__get_shell_command(disk_image, output_file, progress)
        shell_save = subprocess.Popen(cmd_save)

        with open(meta_file, 'w') as f:
            json.dump(disk_meta, f)

    def __add_engine_event(self):
        pass

    def __meta_create(self):
        vm_disks = self.vm_service.disk_attachments_service().list()
        for disk in vm_disks:
            disk_id = disk.id
            disk_info = self.api_service.disks_service().list(search=f'id={disk_id}')
            meta = {
                'interface': disk.interface.value,
                'bootable': int(disk.bootable),
                'active': int(disk.active),
                'read_only': int(disk.read_only),
                'uses_scsi_reservation': int(disk.uses_scsi_reservation),
                'alias': disk_info.alias,
                'description': disk_info.description,
                'id': disk_info.id,
                'provisioned_size': disk_info.provisioned_size,
                'format': disk_info.format.value,
            }
            self.disks_meta[disk_id] = meta

    def __save_vm_settings(self, vm_data, vm_name):
        self.vm_settings = {
            'name': vm_data.name,
            'creation_time': vm_data.creation_time.strftime('%Y.%m.%d %H:%M:%S'),
            'stop_time': vm_data.stop_time.strftime('%Y.%m.%d %H:%M:%S'),
            'stop_reason': vm_data.stop_reason,
            'cluster_id': vm_data.cluster.id,
            'cluster_name': self.__get_cluster_name(vm_data.cluster.id),
            'os_type': vm_data.os.type,
            'optimized': vm_data.type.value,
            'description': vm_data.description,
            'comment': vm_data.comment,
            'memory_size': vm_data.memory,
            'memory_max': vm_data.memory_policy.max,
            'memory_guaranteed': vm_data.memory_policy.guaranteed,
            'memory_ballooning': int(vm_data.memory_policy.ballooning),
            'sockets': vm_data.cpu.topology.sockets,
            'cores': vm_data.cpu.topology.cores,
            'threads': vm_data.cpu.topology.threads,
            'multi_queues': int(vm_data.multi_queues_enabled),
            'virtio_scsi': int(vm_data.virtio_scsi.enabled),
            'io_threads': vm_data.io.threads,
            'numa_tune_mode': vm_data.numa_tune_mode.value,
            'bios_type': vm_data.bios.type.value,
            'time_zone': vm_data.time_zone.name,
            'display_type': vm_data.display.type.value,
            'disconnect_action': vm_data.display.disconnect_action,
            'usb': int(vm_data.usb.enabled),
            'copy_paste': int(vm_data.display.copy_paste_enabled),
            'file_transfer': int(vm_data.display.file_transfer_enabled),
            'smartcard': int(vm_data.display.smartcard_enabled),
            'monitors': vm_data.display.monitors,
            'proxy': vm_data.display.proxy,
            'ha_enabled': int(vm_data.high_availability.enabled),
            'ha_priority': vm_data.high_availability.priority,
            'storage_error_resume': vm_data.storage_error_resume_behaviour.value,
            'affinity': vm_data.placement_policy.affinity.value,
            'auto_converge': vm_data.migration.auto_converge.value,
            'migration_encrypted': vm_data.migration.encrypted.value,
            'migration_compressed': vm_data.migration.compressed.value,
            'start_paused': int(vm_data.start_paused),
            'stateless': int(vm_data.stateless),
        }
        vm_network = dict()
        vm_nic_service = self.vm_service.nics_service()
        for nic in vm_nic_service.list():
            network_id = nic.vnic_profile.id
            network_name = self.__get_nic_profile_name(network_id)
            mac = nic.mac.address
            interface = nic.interface.value
            vm_network[nic.name] = {
                'mac': mac,
                'network_name': network_name,
                'network_id': network_id,
                'interface': interface,
            }

        self.vm_settings['network'] = vm_network

        settings_file = os.path.join(self.vm_backup_dir, vm_name + '.json')
        with open(settings_file, 'w') as f:
            json.dump(self.vm_settings, f)

        ovf_file = os.path.join(self.vm_backup_dir, vm_name + '.ovf')
        data = vm_data.initialization.configuration.data
        with open(ovf_file, 'w') as f:
            f.write(data)


class Restore(Api):
    def __init__(self, settings, task_id):
        super(Restore, self).__init__(settings, task_id)
        self.vm_disks = dict()

    def run(self):
        self.task_settings = self.settings['restore']
        self.__upload_disks()
        if self.task_settings['create_vm']:
            self.__get_vm_settings(self.task_settings['vm_settings'])
            self.__create_vm()
            self.__disk_attachment()
        self.__api_close()

    def __get_vm_settings(self, settings):
        settings_path = os.path.join(self.task_settings['path'], self.task_settings['vm_name'] + '.json')
        with open(settings_path, 'r') as f:
            loaded_settings = json.load(f)
        self.vm_settings = utils.get_vm_options(self.__merge_settings(settings, loaded_settings))

    def __create_vm(self):
        vm = self.vms_service.add(
            vm=types.Vm(
                name=self.vm_settings['name'],
                description=self.vm_settings['description'],
                comment=self.vm_settings['comment'],
                bios=types.Bios(type=self.vm_settings['bios_type']),
                time_zone=types.TimeZone(name=self.vm_settings['time_zone']),
                cluster=types.Cluster(name=self.vm_settings['cluster_name']),
                template=types.Template(name='Blank'),
                os=types.OperatingSystem(
                    type=self.vm_settings['os_type'],
                    boot=types.Boot([types.BootDevice.HD, types.BootDevice.NETWORK, types.BootDevice.CDROM])
                ),
                type=self.vm_settings['optimized'],
                memory=self.vm_settings['memory_size'],
                memory_policy=types.MemoryPolicy(
                    ballooning=self.vm_settings['memory_ballooning'],
                    guaranteed=self.vm_settings['memory_guaranteed'],
                    max=self.vm_settings['memory_max']
                ),
                cpu=types.Cpu(
                    topology=types.CpuTopology(
                        cores=self.vm_settings['cores'],
                        sockets=self.vm_settings['sockets'],
                        threads=self.vm_settings['threads'],
                    )
                ),
                display=types.Display(
                    type=types.DisplayType.SPICE,
                    disconnect_action=self.vm_settings['disconnect_action'],
                    copy_paste_enabled=self.vm_settings['copy_paste'],
                    file_transfer_enabled=self.vm_settings['file_transfer'],
                    smartcard_enabled=self.vm_settings['smartcard'],
                    monitors=self.vm_settings['monitors'],
                ),
                usb=types.Usb(enabled=self.vm_settings['usb']),
                numa_tune_mode=self.vm_settings['numa_tune_mode'],
                io=types.Io(threads=self.vm_settings['io_threads']),
                multi_queues_enabled=self.vm_settings['multi_queues'],
                virtio_scsi=types.VirtioScsi(enabled=self.vm_settings['virtio_scsi']),
                high_availability=types.HighAvailability(
                    enabled=self.vm_settings['ha_enabled'],
                    priority=self.vm_settings['ha_priority'],
                ),
                placement_policy=types.VmPlacementPolicy(affinity=self.vm_settings['affinity']),
                storage_error_resume_behaviour=self.vm_settings['storage_error_resume'],
                migration=types.MigrationOptions(
                    auto_converge=self.vm_settings['auto_converge'],
                    compressed=self.vm_settings['migration_compressed'],
                    encrypted=self.vm_settings['migration_encrypted'],
                ),
                start_paused=self.vm_settings['start_paused'],
                stateless=self.vm_settings['stateless'],
            )
        )
        self.vm_service = self.vms_service.vm_service(vm.id)

    def __disk_attachment(self):
        attachments_service = self.vm_service.disk_attachments_service()
        for disk_id, disk in self.vm_disks.items():
            meta = self.disks_meta[disk_id]
            attachment = attachments_service.add(
                attachment=types.DiskAttachment(
                    disk=types.Disk(
                        id=disk_id,
                    ),
                    active=meta['active'],
                    bootable=meta['bootable'],
                    interface=meta['interface'],
                    read_only=meta['read_only'],
                    uses_scsi_reservation=meta['uses_scsi_reservation'],
                )
            )

    def __network_attach(self):
        vm_nic_service = self.vm_service.nics_service()
        for nic_name, nic_settings in self.vm_settings['network']:
            nic = vm_nic_service.add(
                nic=types.Nic(
                    name=nic_name,
                    interface=nic_settings['interface'],
                    vnic_profile=types.VnicProfile(id=nic_settings['network_id']),
                )
            )

    def __upload_disks(self):
        disks_service = self.api_service.disks_service()
        attachments_service = self.backup_vm_service.disk_attachments_service()

        for disk_name, disk_settings in self.task_settings['disks'].items():
            disk, disk_meta = self.__create_disk(disks_service, disk_name, disk_settings)
            self.__waiting_for_disk_creation(disks_service, disk)
            disk_id = disk.id
            self.vm_disks[disk_id] = disk
            self.disks_meta[disk_id] = disk_meta

            attachment = attachments_service.add(
                attachment=types.DiskAttachment(
                    disk=types.Disk(
                        id=disk_id,
                    ),
                    active=True,
                    bootable=False,
                    interface=types.DiskInterface.VIRTIO,
                )
            )
            attachment_service = attachments_service.attachment_service(attachment.id)
            disk_image = self.__find_disk(attachment)
            self.__load_disk(disk_image, disk_name)
            attachment_service.remove(wait=True)

    def __create_disk(self, disks_service, disk_name, disk_settings):
        disk_path = os.path.join(self.task_settings['path'], disk_name)
        meta_file = disk_path + '.meta'
        with open(meta_file, 'r') as f:
            disk_meta = json.load(f)

        meta = self.__merge_settings(disk_settings, disk_meta)
        meta = utils.get_disk_options(meta)
        disk = disks_service.add(
            disk=types.Disk(
                alias=meta['alias'],
                description=disk_meta['description'],
                format=meta['format'],
                initial_size=meta['provisioned_size'],
                provisioned_size=meta['provisioned_size'],
                storage_domains=[
                    types.StorageDomain(
                        name=meta['storage']
                    )
                ]
            )
        )

        return disk, disk_meta

    @staticmethod
    def __merge_settings(received, loaded):
        result_settings = dict()
        for key, value in received.items():
            result_settings[key] = value if value else loaded[key]

        return result_settings

    def __load_disk(self, disk_image, disk_path):
        progress = os.path.join(self.tmp, self.task_id + '.dat')
        cmd_load = self.__get_shell_command(disk_path, disk_image, progress)
        shell_load = subprocess.call(cmd_load)

    def __waiting_for_disk_creation(self, disks_service, disk):
        disk_service = disks_service.disk_service(disk.id)
        disk_status = types.DiskStatus.LOCKED
        timeout = self.config.get_snapshot_timeout()
        pause = 2
        tries = timeout // pause

        for i in range(tries):
            try:
                disk_status = disk_service.get().status
            except:
                logger.exception('Error getting disk status: ')
            if disk_status == types.DiskStatus.OK:
                break
            time.sleep(pause)
        else:
            logger.error('Disk upload timeout')
