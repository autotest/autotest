import os

class PreconfigManager(object):
    _preconfigs = {}
    _is_init = False

    def _get_preconfig_path(self, suffix):
        """\
        Get the absolute path to a prefix directory or file.

        suffix: list of suffixes after the 'preconfigs' directory to navigate to
            E.g., ['metrics', 'abc'] gives the path to
            <tko>/preconfigs/metrics/abc
        """
        rel_path = os.path.join(os.path.dirname(__file__), 'preconfigs',
                                *suffix)
        return os.path.abspath(rel_path)


    def _init_preconfigs(self):
        """\
        Read the names of all the preconfigs from disk and store them in the
        _preconfigs dictionary.
        """
        if not self._is_init:
            # Read the data
            self._preconfigs['metrics'] = dict.fromkeys(
                os.listdir(self._get_preconfig_path(['metrics'])))
            self._preconfigs['qual'] = dict.fromkeys(
                os.listdir(self._get_preconfig_path(['qual'])))
            self._is_init = True

    def _read_preconfig(self, name, type):
        """\
        Populate the _preconfigs dictionary entry for the preconfig described
        by the given parameters.  If the preconfig has already been loaded,
        do nothing.

        name: specific name of the preconfig
        type: 'metrics' or 'qual'
        """
        if self._preconfigs[type][name] is not None:
            return

        self._preconfigs[type][name] = {}
        path = self._get_preconfig_path([type, name])
        config = open(path)
        try:
            for line in config:
                parts = line.split(':')
                self._preconfigs[type][name][parts[0]] = parts[1].strip()
        finally:
            config.close()


    def get_preconfig(self, name, type):
        self._init_preconfigs()
        self._read_preconfig(name, type)
        return self._preconfigs[type][name]


    def all_preconfigs(self):
        self._init_preconfigs()
        return dict(self._preconfigs)


manager = PreconfigManager()
