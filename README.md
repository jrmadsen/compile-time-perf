# compile-time-perf

This project is designed to be a high-level "profiler" for compiling large projects. It is designed to be included as part of CI.
It is not intended to replace compiler flags like `-ftime-report` or the (phenomenal) `-ftime-trace` provided by newer Clang versions.
The main problem with `-ftime-trace` is that it provides no high-level data w.r.t. which _files_ took the longest to compile, so in
large projects, __*it can be difficult to locate which files are actually taking the longest to compile and which are requiring the most memory to compile.*__
Tools such as [ClangBuildAnalyzer](https://github.com/aras-p/ClangBuildAnalyzer) help locate the files with the longest compilation times by
aggregating multiple trace files but it doesn't provide any information that `-ftime-trace` itself does not provide.

Thus, I created
`compile-time-perf` which essentially uses the UNIX `time` command alongside `rsuage` and some lightweight sampling to read some `/proc/<pid>`
files while the compile command executes and then sticks that data along with the command executed into a JSON file.

## Building CTP

Standard cmake build system without any project-specific options. CTP uses the
[timem](https://github.com/NERSC/timemory/blob/develop/source/tools/timemory-timem/README.md)
([docs](https://timemory.readthedocs.io/en/develop/tools/timemory-timem/README.html))
executable from [timemory toolkit](https://github.com/NERSC/timemory) to do the measurements on the compile commands.
Timemory is included as a git submodule and cmake will automatically run `git submodule update --init` if you don't.

```console
git clone https://github.com/jrmadsen/compile-time-perf.git compile-time-perf-source
cmake -B compile-time-perf-build compile-time-perf-source
cmake --build compile-time-perf-build --target all
cmake --build compile-time-perf-build --target install
```

Minimum requirements:

- CMake (minimum: v3.13)
- C++ compiler supporting C++14
- Python interpreter

> __*CTP is not supported on Windows currently*__. It can be made available fairly easily
> if someone wants to contribute the equivalent of `fork()` + `execve()` on Windows to the `timem` executable.

## Quick Start

compile-time-perf (CTP) is designed primarily for CMake but if you want to use it manually, see the [Manual Usage](#manual-usage) section.

### Setup

Add this to your main CMakeLists.txt somewhere after `project(...)`. I'd recommend replacing `foo` below with `${PROJECT_NAME}`.

```cmake
find_package(compile-time-perf REQUIRED)
enable_compile_time_perf(foo-ctp)
```

or, making it optional:

```cmake
find_package(compile-time-perf)
if(compile-time-perf_FOUND)
    enable_compile_time_perf(foo-ctp)
endif()
```

The argument `foo-ctp` is just a "NAME" used to generate two "helper" targets: one for running the analysis (`analyze-${NAME}`) and another for cleaning up the generated files (`clean-${NAME}`).

### Building and Analyzing

Once you've added the [cmake setup](#setup), configure and build your code normally, and then build the `analyze-${NAME}` target, e.g. `analyze-foo-ctp`.

```console
$ cmake --build . --target all

[1/81] Building CXX object source/timemory/CMakeFiles/timemory-core-shared.dir/utility/popen.cpp.o
[/opt/local/bin/clang++]> Outputting '.compile-time-perf-timem-output/foo-ctp-33ce7f2719c9a3f0a9147cf3f1dfc242.json'...
...

$ cmake --build . --target analyze-foo-ctp

wall_clock          74.947 sec  clang++ tools/timemory-avail/timemory-avail.cpp
wall_clock          42.742 sec  clang++ tools/timemory-timem/timem.cpp
wall_clock           4.092 sec  clang++ tools/timemory-pid/timemory-pid.cpp

cpu_clock          74.150 sec  clang++ tools/timemory-avail/timemory-avail.cpp
cpu_clock          41.970 sec  clang++ tools/timemory-timem/timem.cpp
cpu_clock           3.680 sec  clang++ tools/timemory-pid/timemory-pid.cpp

peak_rss        2040.410 MB   clang++ tools/timemory-avail/timemory-avail.cpp
peak_rss        1040.617 MB   clang++ tools/timemory-timem/timem.cpp
peak_rss         194.691 MB   clang++ tools/timemory-pid/timemory-pid.cpp
```

> NOTE: The JSON filename (e.g. `33ce...c242.json` above) is just the md5sum of the compile command without spaces, e.g. for the command `g++ foo.cpp -o foo`, the md5sum is computed from `g++foo.cpp-ofoo`. This is used to ensure uniqueness and reproducibility.

### Advanced Tutorial

In CMake, CTP uses what is called the `RULE_LAUNCH_COMPILE` property to prefix every compile command and `enable_compile_time_perf(...)` is a CMake macro that sets it.
This macro has quite a few features to enable getting the exact amount of information emitted during CI. For example, you may want to create a CTest
which depends on the `all` target being built and you want the compile command to print an abbreviated path and include the optimization/arch flags
so that you can set `FAIL_REGULAR_EXPRESSION` if the build time exceeded the range defined in the expression.
In other words, if the failure case is the wall-clock compile time exceeding 30 seconds with the clang compiler and `-O3 -march=native`,
transforming `clang++ source/tools/timemory-timem/timem.cpp` into rendering `clang++ -O3 -march=native timem.cpp` for
`^wall_clock    [3-9][0-9].([0-9]+) sec  clang.. -O3 -march=native timem.cpp"` is supported.

- It can be applied globally, per-project, per-directory, and/or per-target
  - `GLOBAL` (zero args)
  - `PROJECT` (zero args)
  - `DIRECTORY` (1+ args)
  - `TARGET` (1+ args)
- You can pass options to timem
  - `TIMEM_OPTIONS` (1+ args)
  - See `timem --help`
- You can pass options to the python analysis script
  - `ANALYZER_OPTIONS` (1+ args)
  - See `compile-time-perf-analyzer --help`
- You can prefix link commands as well as compile commands
  - `LINK` (zero args)
- You can customize the output directory
  - `TIMEM_OUTPUT_DIRECTORY` (one arg)

```cmake
add_library(foo ...)

enable_compile_time_perf(foo-ctp
    LINK                                    # include link command
    TARGET
        foo                                 # only apply to foo target
    TIMEM_OPTIONS
        --disable-sampling                  # disable timem sampling /proc/pid on Linux
    ANALYZER_OPTIONS                        #
        -m wall_clock peak_rss cpu_clock    # only report these metrics
        -s "${PROJECT_SOURCE_DIR}/"         # remove this strings from prefix/suffix
        -i "^(-D).*"                        # include the compile definitions in the labels
        -n 5                                # only show first 5 entries
    )

# enable unity builds
set(CMAKE_UNITY_BUILD ON)

add_library(bar ...)

enable_compile_time_perf(bar-ctp
    TARGET
        bar
    ANALYZER_OPTIONS
        -r ".dir/Unity/unity_[0-9]_(cxx|cpp).(cxx|cpp)" # remove unity build generated path
        -i "^(-).*"             # include everything starting with hyphen in label
        -e "^(-D).*(_EXPORTS)$" # except for definitions ending with _EXPORTS
    )
```

## Manual Usage

CTP installs a simple Python script called `compile-time-perf-analyzer`. Usage is fairly staight-forward.

```console
$ compile-time-perf-analyzer --help
usage: compile-time-perf-analyzer [-h] [-v] [-n MAX_ENTRIES] [-i [INCLUDE_REGEX [INCLUDE_REGEX ...]]]
                                  [-e [EXCLUDE_REGEX [EXCLUDE_REGEX ...]]] [-f [FILE_EXTENSIONS [FILE_EXTENSIONS ...]]]
                                  [-s [STRIP [STRIP ...]]] [-r [REGEX_STRIP [REGEX_STRIP ...]]] [-m METRIC [METRIC ...]]
                                  [-l]
                                  [inputs [inputs ...]]

Measures high-level timing and memory usage metrics during compilation

positional arguments:
    inputs                                      List of JSON files or directory containing JSON files from timem

optional arguments:
    -h, --help                                  show this help message and exit
    -v, --verbose, --debug                      Print out verbosity messages (i.e. debug messages)
    -n MAX_ENTRIES                              Max number of entries to display
    -i [INCLUDE_REGEX [INCLUDE_REGEX ...]]      List of regex expressions for including command-line arguments
    -e [EXCLUDE_REGEX [EXCLUDE_REGEX ...]]      List of regex expressions for removing command-line arguments
    -f [FILE_EXTENSIONS [FILE_EXTENSIONS ...]]  List of file extensions (w/o period) to include in label. Use 'lang-c',
                                                'lang-cxx', 'lang-fortran' keywords to include common extensions. Use
                                                'lang-all' to include all defaults. Use 'none' to disable all extension
                                                filtering
    -s [STRIP [STRIP ...]]                      List of string to strip from the start/end of the labels
    -r [REGEX_STRIP [REGEX_STRIP ...]]          List of regular expressions to strip from the start/end of the labels
    -m METRIC [METRIC ...]                      List of metrics to display
    -l, --list-metrics                          List the metrics which can be potentially reported and exit

All arguments after standalone '--' are treated as input files/directories, e.g. ./foo <options> -- bar.txt baz/
```

In order to generate the JSON files for the Python script, just prefix every compile command with `timem -o <DIR>/%m -q --`
where `<DIR>` is the common directory for the output files, `%m` instructs timem to generate an md5sum of everything after
the `--`, `-q` just instructs timem to not output to console.

```shell
# original command
g++ foo.cpp -o foo

# manual command
timem -o foo-ctp/%m -q -- g++ foo.cpp -o foo
```
