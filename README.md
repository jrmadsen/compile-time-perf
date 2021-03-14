# compile-time-perf

I work with a lot of larger projects and do a lot of template meta-programming so while I absolutely love the flamegraphs from
the `-ftime-trace` compiler flag, I've had a hard time detecting when changes affect the total compilation time and which
files saw the most dramatic increase/decrease in compile time.

Thus, I created `compile-time-perf` (CTP), which is designed to be a high-level "profiler" for compiling large projects.
__*It is designed to be simple to install, compiler and language agnostic, and included as part of CI.*__
It is not intended to replace compiler flags like `-ftime-trace` but supplement them.
The main problem with `-ftime-trace` is that it provides no high-level data w.r.t. _which_ files to focus on, so in large projects,
it can be difficult to locate which file should be focused on first. Another problem is that it only provides timing data --
if the system has limited memory resources but has 4+ cores, your compile times can shoot up drastically if each core is compiling
something requiring 2+ GB of memory because you'll start using swap.

Down the road, I could see the "analyzer" script actually including support for detecting `-ftime-trace` in the compile command
logs, searching the folder structure for the JSON, and then using/providing something like
[ClangBuildAnalyzer](https://github.com/aras-p/ClangBuildAnalyzer) to provide more in-depth details.
But I think the useful enough by itself right now.

CTP essentially uses a UNIX `time`-like command-line tool to launch the compile commands, called
[timem](https://github.com/NERSC/timemory/blob/develop/source/tools/timemory-timem/README.md)
([docs](https://timemory.readthedocs.io/en/develop/tools/timemory-timem/README.html)),
which I built using the [timemory toolkit](https://github.com/NERSC/timemory) --
a modular C++ template library for build profiling tools which, recursively, is one of the two primary places
where I need this functionality (other is [Kokkos](https://github.com/kokkos/kokkos)).

Timem does do anything particularly fancy: it just forks and does a mix of deterministic phase measurements and
(on Linux) some statistical sampling of a few `/proc/<pid>` files while the command executes. Then that data along
with the command executed are put into a JSON file whose name is generated from an md5sum of command executed
(for uniqueness and reproducibility). Then the Python "analyzer" script just globs the files and directories it is
passed and combines that data, does some sorting and filtering to make the commands more easily readable and thats it.

## Building CTP

Standard cmake build system without any project-specific options.
CTP uses the [timem](https://github.com/NERSC/timemory/blob/develop/source/tools/timemory-timem/README.md)
executable from the [timemory toolkit](https://github.com/NERSC/timemory) to do the measurements on the compile commands.
[Timemory](https://timemory.readthedocs.io/en/develop/) is included as a git submodule and
cmake will automatically run `git submodule update --init` if you don't.

```console
# clone
git clone https://github.com/jrmadsen/compile-time-perf.git
# configure (it's not hanging, timemory can take a while here)
cmake -B compile-time-perf-build -D CMAKE_INSTALL_PREFIX=/usr/local compile-time-perf
# build
cmake --build compile-time-perf-build --target all
# install
cmake --build compile-time-perf-build --target install
```

When configuring your project, just set append the CMAKE_INSTALL_PREFIX value to the CMAKE_PREFIX_PATH environment variable.

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
