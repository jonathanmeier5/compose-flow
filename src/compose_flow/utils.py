import re
import os
import sys

from boltons.iterutils import remap, get_path, default_enter, default_visit

from .errors import EnvError, ProfileError

# regular expression for finding variables in docker compose files
VAR_RE = re.compile(r'\${(?P<varname>.*)}')


# https://gist.github.com/mahmoud/db02d16ac89fa401b968
def remerge(target_list, sourced=False):
    """Takes a list of containers (e.g., dicts) and merges them using
    boltons.iterutils.remap. Containers later in the list take
    precedence (last-wins).
    By default, returns a new, merged top-level container. With the
    *sourced* option, `remerge` expects a list of (*name*, container*)
    pairs, and will return a source map: a dictionary mapping between
    path and the name of the container it came from.
    """

    if not sourced:
        target_list = [(id(t), t) for t in target_list]

    ret = None
    source_map = {}

    def remerge_enter(path, key, value):
        new_parent, new_items = default_enter(path, key, value)
        if ret and not path and key is None:
            new_parent = ret
        try:
            cur_val = get_path(ret, path + (key,))
        except KeyError:
            pass
        else:
            # TODO: type check?
            new_parent = cur_val

        if isinstance(value, list):
            # lists are purely additive. See https://github.com/mahmoud/boltons/issues/81
            new_parent.extend(value)
            new_items = []

        return new_parent, new_items

    for t_name, target in target_list:
        if sourced:
            def remerge_visit(path, key, value):
                source_map[path + (key,)] = t_name
                return True
        else:
            remerge_visit = default_visit

        ret = remap(target, enter=remerge_enter, visit=remerge_visit)

    if not sourced:
        return ret
    return ret, source_map


def render(content):
    """
    Renders the variables in the file
    """
    previous_idx = 0
    rendered = ''
    for x in VAR_RE.finditer(content):
        rendered += content[previous_idx:x.start('varname')-2]  # -2 to get rid of variable's `${`

        varname = x.group('varname')
        try:
            rendered += os.environ[varname]
        except KeyError:
            raise EnvError(f'Error: varname={varname} not in environment; cannot render')

        previous_idx = x.end('varname') + 1  # +1 to get rid of variable's `}`

    rendered += content[previous_idx:]

    return rendered
