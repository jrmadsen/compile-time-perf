#!/usr/bin/env python

import os
import re
import sys
import glob
import json
import argparse


_verbose = False

_c_extensions = ["c", "C"]

_cpp_extensions = [
    "cpp",
    "c++",
    "cc",
    "cp",
    "cxx",
    "h",
    "h++",
    "hh",
    "hpp",
    "hxx",
    "inc",
    "inl",
    "ipp",
    "tcc",
    "tpp",
]

_fortran_extensions = [
    "f90",
    "f",
    "f03",
    "f08",
    "f77",
    "f95",
    "for",
    "fpp",
]

_misc_extensions = [
    "cu",  # CUDA
    "upc",  # UPC
    "upcxx",  # UPC++
]

_default_extensions = (
    _c_extensions + _cpp_extensions + _fortran_extensions + _misc_extensions
)


def log_message(msg):
    """Prints a log message"""
    if _verbose:
        sys.stderr.write("{}\n".format(msg))


class Measurement(object):
    def __init__(self, _name, _compiler, _cmd, _data):
        def strip_common_prefix(_files):
            _tmp = []
            _orig = []
            for itr in _files:
                if os.path.isfile(itr):
                    log_message(f"file: {itr}")
                    itr = os.path.abspath(itr)
                    _tmp.append(itr)
                else:
                    _orig.append(itr)

            commonp = os.path.commonprefix(_tmp)
            log_message(f"common prefix: {commonp}")
            if commonp == "/" or len(commonp) == 0:
                for itr in _tmp:
                    itr = "/.../{}".format(
                        os.path.join(
                            os.path.basename(os.path.dirname(itr)),
                            os.path.basename(itr),
                        )
                    )
            else:
                if len(_tmp) > 0 and len(commonp) < len(
                    os.path.dirname(_tmp[0])
                ):
                    _tmp = [x[len(commonp) :] for x in _tmp]
            return sorted(_orig + _tmp)

        self.name = _name
        self.compiler = _compiler
        self.command = strip_common_prefix(_cmd)
        self.value = _data["value"]
        self.units = _data["unit_repr"]
        self.samples = _data["laps"]
        self.files_in_command = []
        for itr in _cmd:
            if os.path.isfile(itr):
                self.files_in_command.append(itr)
        self.files_in_command = strip_common_prefix(self.files_in_command)

    def __lt__(self, rhs):
        return self.value < rhs.value

    def __str__(self):
        return "{} {}".format(self.value, self.units)


def main(data, args):
    common = []
    compiler = []
    config = []
    commands = []
    measurements = {}

    # compile the regex expressions ahead of time
    include_regex = None
    exclude_regex = None
    if args.include_regex:
        _include = "|".join(args.include_regex)
        log_message("compiling exclude regex: {}".format(_include))
        include_regex = re.compile(_include)

    if args.exclude_regex:
        _exclude = "|".join(args.exclude_regex)
        log_message("compiling exclude regex: {}".format(_exclude))
        exclude_regex = re.compile(_exclude)
        del _exclude

    def ignore_arg(x):
        """Series of checks for whether to remove or include
        the argument in the label"""
        # prioritize removal
        log_message(f"checking arg: '{x}'...")
        if exclude_regex is not None:
            if exclude_regex.match(x):
                log_message(f"{x} statisfied the exclude regex. Discarding...")
                return True
        # check the extension
        if args.extensions.search(x) is not None:
            log_message(
                f"{x} statisfied the file extension regex. Including..."
            )
            return False
        # check the include regex last
        if include_regex is not None:
            if include_regex.match(x) is not None:
                log_message(f"{x} statisfied the include regex. Including...")
                return False

        log_message(f"{x} was not explicitly included/excluded. Discarding...")
        return True

    for itr in data:
        if not isinstance(itr, dict):
            raise RuntimeError(
                "Expected dictionary but got {} from {}".format(
                    type(itr).__name__, itr
                )
            )
        if "timemory" not in itr:
            log_message(
                "JSON entry does not start with timemory. Ignoring {}".format(
                    itr
                )
            )
            continue
        itr = itr["timemory"]
        # first argument will be timem
        # second arg will be command
        comp = itr["command_line"][1]
        # store the rest of the command line
        cmd = sorted(itr["command_line"][2:])
        compiler.append(comp)
        commands.append(cmd)
        config.append(itr["config"])
        itr = itr["timem"]
        cmd = [x for x in cmd if not ignore_arg(x)]
        for entry in itr:
            for name, data in entry.items():
                if name not in args.metrics:
                    log_message(f"Ignoring metric {name}...")
                    continue
                if name not in measurements:
                    measurements[name] = []
                mitr = measurements[name]
                mitr.append(Measurement(name, comp, cmd, data))

    # find the common set of command flags
    common = []
    if len(commands) > 0:
        common = commands[0]
        for itr in commands[1:]:
            common = list(set(common).intersection(itr))
    else:
        log_message("No common commands in {}".format(commands))

    # report the common set of arguments
    print("\nCommon arguments to all commands:")
    for itr in sorted(common):
        print("    {:12}".format(itr))

    strip_regex = []
    for itr in args.regex_strip:
        log_message(
            "Adding strip regular expressions '{0}$' and '^{0}'...".format(itr)
        )
        strip_regex.append(re.compile("{}$".format(itr)))
        strip_regex.append(re.compile("^{}".format(itr)))

    for key, data in measurements.items():
        # report the arguments that are not in the common set
        for itr in data:
            itr.command = list(set(itr.command).difference(common))
        data = [x for x in data if x.value > 0]
        data = sorted(data)
        data.reverse()
        if args.max_entries > 0:
            data = data[0 : (args.max_entries)]
        if len(data) > 0:
            print("")  # separator
            for itr in data:
                cmd = []
                for citr in itr.command:
                    val = citr
                    for sitr in args.strip:
                        val = val[len(sitr):] if val.startswith(sitr) else val
                        val = val[:len(val)-len(sitr)] if val.endswith(sitr) else val
                    for ritr in strip_regex:
                        val = ritr.sub("", val, count=1)
                    cmd.append(val)
                cmd = sorted(cmd)
                if len(cmd) == 0:
                    cmd = itr.files_in_command
                if isinstance(itr.value, float):
                    print(
                        "{}    {:12.3f} {:4} {} {:40s}".format(
                            key,
                            itr.value,
                            itr.units,
                            os.path.basename(itr.compiler),
                            " ".join(cmd),
                        )
                    )
                else:
                    print(
                        "    {:12} {:4} {} {:40s}".format(
                            itr.value,
                            itr.units,
                            os.path.basename(itr.compiler),
                            " ".join(cmd),
                        )
                    )


class Formatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog, *args, **kwargs):
        _cols = 120
        try:
            _cols = min([os.get_terminal_size().columns, _cols])
        except OSError:
            pass

        kwargs["indent_increment"] = 4
        kwargs["max_help_position"] = 60
        kwargs["width"] = _cols
        super(Formatter, self).__init__(prog, *args, **kwargs)


if __name__ == "__main__":

    extension_keywords = {
        "lang-all": _default_extensions,
        "lang-c": _c_extensions,
        "lang-cxx": _cpp_extensions,
        "lang-fortran": _fortran_extensions,
    }

    metric_choices = (
        "wall_clock",
        "cpu_clock",
        "peak_rss",
        "page_rss",
        "virtual_memory",
        "user_clock",
        "system_clock",
        "cpu_util",
        "num_major_page_faults",
        "num_minor_page_faults",
        "priority_context_switch",
        "voluntary_context_switch",
        "read_char",
        "read_bytes",
        "written_char",
        "written_bytes",
    )

    parser = argparse.ArgumentParser(
        "compile-time-perf-analyzer",
        description=(
            "Measures high-level timing and memory usage metrics "
            "during compilation"
        ),
        epilog=(
            "All arguments after standalone '--' are treated as "
            "input files/directories, e.g. ./foo <options> -- bar.txt baz/"
        ),
        formatter_class=Formatter,
    )

    parser.add_argument(
        "inputs",
        nargs="*",
        type=str,
        help=(
            "List of JSON files or directory containing JSON files from "
            "timem"
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        "--debug",
        dest="verbose",
        action="store_true",
        help="Print out verbosity messages (i.e. debug messages)",
    )
    parser.add_argument(
        "-n",
        dest="max_entries",
        type=int,
        help="Max number of entries to display",
        default=0,
    )
    parser.add_argument(
        "-i",
        dest="include_regex",
        type=str,
        nargs="*",
        help="List of regex expressions for including command-line arguments",
        default=None,
    )
    parser.add_argument(
        "-e",
        dest="exclude_regex",
        type=str,
        nargs="*",
        help="List of regex expressions for removing command-line arguments",
        default=None,
    )
    parser.add_argument(
        "-f",
        dest="file_extensions",
        type=str,
        nargs="*",
        help=(
            "List of file extensions (w/o period) to include in label. "
            "Use 'lang-c', 'lang-cxx', 'lang-fortran' keywords "
            "to include common extensions. Use 'lang-all' to include all "
            "defaults. Use 'none' to disable all extension filtering"
        ),
        default=["lang-all"],
    )
    parser.add_argument(
        "-s",
        dest="strip",
        type=str,
        nargs="*",
        help="List of string to strip from the start/end of the labels",
        default=[],
    )
    parser.add_argument(
        "-r",
        dest="regex_strip",
        type=str,
        nargs="*",
        help=(
            "List of regular expressions to strip from the start/end of "
            "the labels"
        ),
        default=[],
    )
    parser.add_argument(
        "-m",
        dest="metrics",
        nargs="+",
        type=str,
        help="List of metrics to display",
        default=[
            "wall_clock",
            "cpu_clock",
            "peak_rss",
            "virtual_memory",
        ],
        metavar="METRIC",
        choices=metric_choices,
    )
    parser.add_argument(
        "-l",
        "--list-metrics",
        action="store_true",
        help="List the metrics which can be (potentially) reported and exit",
    )

    _iargs = None  # input args
    _dargs = []  # args after "--"
    if "--" in sys.argv:
        _idx = sys.argv.index("--")
        _iargs = sys.argv[1:_idx]
        _dargs += sys.argv[(_idx + 1) :]
    else:
        _iargs = sys.argv[1:]

    args = parser.parse_intermixed_args(_iargs)

    if args.list_metrics:
        log_message(
            "Metrics supported this script may not be reported by timem "
            "due to that metric being unavailable for collection."
        )
        for m in metric_choices:
            print(f"    {m}")
        sys.exit(0)

    _verbose = args.verbose
    log_message(f"arguments: {args}")
    paths = _dargs + args.inputs
    files = []
    for itr in paths:
        if os.path.isfile(itr):
            files.append(itr)
        elif os.path.isdir(itr):
            for fitr in glob.glob(os.path.join(itr, "*.json")):
                if os.path.isfile(fitr):
                    files.append(os.path.realpath(fitr))
        else:
            for fitr in glob.glob(f"{itr}*.json"):
                if os.path.isfile(fitr):
                    files.append(os.path.realpath(fitr))

    if len(files) == 0:
        raise RuntimeError(
            "No files were found in {}".format(", ".join(paths))
        )

    data = []
    for itr in files:
        log_message(f"Reading file: {itr}")
        with open(itr, "r") as f:
            data.append(json.load(f))

    if len(data) == 0:
        raise RuntimeError(
            "No files were found in {}".format(", ".join(paths))
        )

    # only matches empty strings
    args.extensions = re.compile("^$")
    if "none" not in args.file_extensions:
        extensions = args.file_extensions
        # keyword based extensions
        for key, ext in extension_keywords.items():
            if key in args.file_extensions:
                extensions += ext
        # remove keywords
        extensions = [
            x for x in extensions if x not in extension_keywords.keys()
        ]
        # remove duplicates and sort
        extensions = sorted(list(set(extensions)))
        log_message("Extensions: '{}'".format(extensions))
        # convert to regular expression
        _re_extensions = ".*\\.({})$".format(
            "|".join(extensions).replace(".", "\\.").replace("+", "\+")
        )
        log_message(f"Extension regex pattern: '{_re_extensions}'")
        args.extensions = re.compile(_re_extensions)

    main(data, args)
