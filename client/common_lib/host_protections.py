import enum, global_config

Protection = enum.Enum('No protection',          # Repair can do anything to
                                                 # this host.
                       'Repair software only',   # repair should try to fix any
                                                 # software problem
                       'Repair filesystem only', # Repair should only try to
                                                 # recover the file system.
                       'Do not repair'           # Repair should not touch this
                                                 # host.
                       )

default = Protection.get_value(
    global_config.global_config.get_config_value(
        'HOSTS', 'default_protection'))

choices = Protection.choices()
