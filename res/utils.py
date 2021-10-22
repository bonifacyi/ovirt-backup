from ovirtsdk4 import types

COMPRESS_TYPES = {
    "off": ("", [], []),
    "gzip": (".gzip", ["gzip", "-c"], ["gunzip", "-c"]),
    "bzip2": (".bzip2", ["bzip2", "-c"], ["bzip2", "-d"]),
    "lzo": (".lzo", ["lzop", "-c"], ["lzop", "-d"]),
    "lzma": (".lzma", ["lzma", "-c"], ["unlzma", "-c"]),
    "xz": (".xz", ["xz", "-c"], ["xz", "-d"]),
    "pbzip2": (".pbzip2", ["pbzip2", "-c"], ["pbzip2", "-d"])
}
DISK_FORMAT = {
    'cow': types.DiskFormat.COW,
    'raw': types.DiskFormat.RAW
}
DISK_INTERFACE = {
    'virtio_scsi': types.DiskInterface.VIRTIO_SCSI,
    'virtio': types.DiskInterface.VIRTIO,
    'sata': types.DiskInterface.SATA,
    'ide': types.DiskInterface.IDE,
    'spapr_vscsi': types.DiskInterface.SPAPR_VSCSI,
}
OPTIMIZED = {
    'desktop': types.VmType.DESKTOP,
    'server': types.VmType.SERVER,
    'high_performance': types.VmType.HIGH_PERFORMANCE,
}
DISPLAY = {
    'spice': types.DisplayType.SPICE,
    'vnc': types.DisplayType.VNC,
}
AFFINITY = {
    'migratable': types.VmAffinity.MIGRATABLE,
    'pinned': types.VmAffinity.PINNED,
    'user_migratable': types.VmAffinity.USER_MIGRATABLE,
}
BOOLEAN = {
    'inherit': types.InheritableBoolean.INHERIT,    # auto_converge, encrypted
    'true': types.InheritableBoolean.TRUE,
    'false': types.InheritableBoolean.FALSE,
}
STORAGE_ERROR_RESUME = {
    'auto_resume': types.VmStorageErrorResumeBehaviour.AUTO_RESUME,
    'kill': types.VmStorageErrorResumeBehaviour.KILL,
    'leave_paused': types.VmStorageErrorResumeBehaviour.LEAVE_PAUSED,
}
BIOS_TYPE = {
    'cluster_default': types.BiosType.CLUSTER_DEFAULT,
    'q35_sea_bios': types.BiosType.Q35_SEA_BIOS,
    'i440fx_sea_bios': types.BiosType.I440FX_SEA_BIOS,
    'q35_ovmf': types.BiosType.Q35_OVMF,
    'q35_secure_boot': types.BiosType.Q35_SECURE_BOOT,
}
NUMA_TUNE_MODE = {
    'interleave': types.NumaTuneMode.INTERLEAVE,
    'preferred': types.NumaTuneMode.PREFERRED,
    'strict': types.NumaTuneMode.STRICT,
}
NIC_INTERFACE = {
    'virtio': types.NicInterface.VIRTIO,
    'e1000': types.NicInterface.E1000,
    'pci_passthrough': types.NicInterface.PCI_PASSTHROUGH,
    'rtl8139': types.NicInterface.RTL8139,
    'rtl8139_virtio': types.NicInterface.RTL8139_VIRTIO,
    'spapr_vlan': types.NicInterface.SPAPR_VLAN,
}
BOOLEAN_OPTIONS = {
    'memory_ballooning',
    'multi_queues',
    'usb',
    'copy_paste',
    'file_transfer',
    'smartcard',
    'high_availability_enabled',
    'start_paused',
    'stateless',
    'virtio_scsi',
}


def get_backup_command(input_file, output_file, compress, progress, save, remote=False):
    # cmd = ['qemu-img', 'convert', '-U', '-O', 'qcow2', disk_image, output_file]
    compress_types = {
        "off": ("", [], []),
        "gzip": (".gzip", ["|", "gzip", "-c"], ["|", "gunzip", "-c"]),
        "bzip2": (".bzip2", ["|", "bzip2", "-c"], ["|", "bzip2", "-d"]),
        "lzo": (".lzo", ["|", "lzop", "-c"], ["|", "lzop", "-d"]),
        "lzma": (".lzma", ["|", "lzma", "-c"], ["|", "unlzma", "-c"]),
        "xz": (".xz", ["|", "xz", "-c"], ["|", "xz", "-d"]),
        "pbzip2": (".pbzip2", ["|", "pbzip2", "-c"], ["|", "pbzip2", "-d"])
    }
    if save:
        output_file += compress_types[compress][0]
        cmd_compress = compress_types[compress][1]
    else:
        input_file += compress_types[compress][0]
        cmd_compress = compress_types[compress][2]
    cmd_ssh = []
    cmd_pv = ['pv', '-n', input_file]
    cmd_dd = ['|', 'dd', 'bs=1M', 'conv=notrunc,noerror', 'status=none', 'of='+output_file]
    cmd_progress = ['>', progress, '2>&1']

    cmd = cmd_ssh + ['('] + cmd_pv + cmd_compress + cmd_dd + [')'] + cmd_progress
    return cmd


def list_to_dict(arr):
    dictionary = dict()
    if len(arr):
        i = 0
        for item in arr:
            dictionary[i] = item
            i += 1
    return dictionary


def get_disk_options(arr):
    settings = dict(arr)
    settings['format'] = DISK_FORMAT[settings['format']]
    settings['interface'] = DISK_INTERFACE[settings['interface']]
    return settings


def get_vm_options(arr):
    settings = dict(arr)
    settings['optimized'] = OPTIMIZED[settings['optimized']]
    settings['display_type'] = DISPLAY[settings['display_type']]
    settings['affinity'] = AFFINITY[settings['affinity']]
    settings['storage_error_resume'] = STORAGE_ERROR_RESUME[settings['storage_error_resume']]
    settings['bios_type'] = BIOS_TYPE[settings['bios_type']]
    settings['numa_tune_mode'] = NUMA_TUNE_MODE[settings['numa_tune_mode']]
    settings['auto_converge'] = BOOLEAN[settings['auto_converge']]
    settings['migration_encrypted'] = BOOLEAN[settings['migration_encrypted']]
    settings['migration_compressed'] = BOOLEAN[settings['migration_compressed']]

    for name in settings['network'].keys():
        settings['network'][name]['interface'] = NIC_INTERFACE[settings['network'][name]['interface']]

    for option in settings.keys():
        if option in BOOLEAN_OPTIONS:
            settings[option] = bool(settings[option])

    return settings
