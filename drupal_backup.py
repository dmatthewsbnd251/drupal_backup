DOCUMENTATION = '''
---
module: drupal_backup
short_description: Backup your drupal databases
'''

from ansible.module_utils.basic import *
import os
import time
import stat
import subprocess

search_params = ('database', 'username', 'password', 'host', 'port')


def parse_settings_file(settings_file):
    db_connection_settings = dict()
    with open(settings_file, 'r') as s_file:
        for line in s_file:
            if '=>' in line:
                split_line = line.split()
                #config file has values like 'database' so dropping the single quotes
                param_name = split_line[0].strip("'")
                if param_name in search_params:
                    param_value = split_line[2].strip("',")
                    db_connection_settings[param_name] = param_value
    return db_connection_settings


def get_database_settings(drupal_path):
    my_settings_files=dict()
    for root, dirs, files in os.walk(drupal_path):
        for file in files:
            if 'settings.php' == file:
                file_full_path = os.path.join(root, file)
                my_settings_files[file_full_path]=parse_settings_file(file_full_path)
    return my_settings_files


def file_age_in_seconds(pathname):
    return time.time() - os.stat(pathname)[stat.ST_MTIME]


def sanity_check_db_settings(db_settings):
    for s_param in search_params:
        if s_param not in db_settings.keys():
            return False
    return True


def drupal_backup_present(data):
    drupal_path = data['drupal_path']
    backup_path = data['backup_path']
    max_age_seconds = data['max_age_seconds']
    changed = False

    settings_files = get_database_settings(drupal_path)

    for settings_file in settings_files:
        if not sanity_check_db_settings(settings_files[settings_file]):
            return True, False, {"status": "Bad settings file found at: %s" % settings_file}

        database = settings_files[settings_file]['database']
        username = settings_files[settings_file]['username']
        password = settings_files[settings_file]['password']
        host = settings_files[settings_file]['host']
        port = settings_files[settings_file]['port']

        backup_file = backup_path.rstrip('/')+'/'+database+'.sql'

        if not os.path.isfile(backup_file) or \
                (os.path.isfile(backup_file) and file_age_in_seconds(backup_file) > max_age_seconds):

            with open(backup_file, "wb") as outfile:
                process = subprocess.Popen(['mysqldump', '-u', username, '-p'+password, '-h'+host, '-P'+str(port),
                                            '--single-transaction', database,],
                                           stdout=outfile,
                                           stderr=subprocess.PIPE)
                process.communicate()
                changed = True

    return False, changed, {"status": "Success"}


def drupal_backup_absent(data):
    drupal_path = data['drupal_path']
    backup_path = data['backup_path']
    changed = False
    settings_files = get_database_settings(drupal_path)
    for settings_file in settings_files:
        database = settings_files[settings_file].get('database', None)
        if database is not None:
            backup_file = backup_path.rstrip('/')+'/'+database+'.sql'
            if os.path.exists(backup_file):
                os.remove(backup_file)
                changed = True
    return False, changed, {"status": "Success"}


def main():

    fields = {
        "drupal_path": {"required": True, "type": "str"},
        "backup_path": {"required": True, "type": "str"},
        "max_age_seconds": {"required": False, "type": "int", "default": 600},
        "state": {
            "default": "present",
            "choices": ['present', 'absent'],
            "type": 'str'
        },
    }

    choice_map = {
        "present": drupal_backup_present,
        "absent": drupal_backup_absent,
    }

    module = AnsibleModule(argument_spec=fields)
    is_error, has_changed, result = choice_map.get(module.params['state'])(module.params)

    if not is_error:
        module.exit_json(changed=has_changed, meta=result)
    else:
        module.fail_json(msg="Error with drupal_backup module", meta=result)


if __name__ == '__main__':
    main()