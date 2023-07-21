"""Explore a file structure and build of distribution of file numbers and file size."""
from __future__ import annotations

import argparse
import configparser
import logging
import re
from pathlib import Path

from _parser import Parser
from file_tree import FileTree
from identifierEngine import IdentifierEngine
from smartDirectoryPath import SmartDirectoryPath
from smartFilePath import SmartFilePath
from smartPath import SmartPath
from statBuilder import StatBuilder

# Edit the following line to point to the config file location in your current installation:
CONFIG_PATH = Path(__file__).parent / "config.ini"
LOGGER_NAME = "file_tree_check"
LOGGER_FILE_FORMAT = "%(asctime)s %(name)-12s %(levelname)-8s %(message)s"
LOGGER_CONSOLE_FORMAT = "%(name)-12s %(levelname)-8s %(message)s"
FILENAME_MAX_LENGTH = 60


def _arg_parser():
    """Extract the arguments given to the script.

    Arguments are the part given after the main.py call in the command line.

    Only 1 required argument:
    the path to the folder to be used as the root for the analysis.
    2 optional and mutually exclusive arguments:
    "verbose" and "debug" to print logs of various levels to the console.

    If neither "verbose" nor "debug" is given, logs will not be output
    to the console (or other standard output)
    although they could be saved in a file via an option in the config files.
    "debug" will show more detailed information to the console compared to "verbose".
    Activating the log to console with either "verbose" or "debug"
    is independent and not mutually exclusive to the logs to file.

    Returns
    -------
    argparse.ArgumentParser
        A parser object to be used in main() containing the argument data.
    """
    pars = argparse.ArgumentParser(description="Insert doc here")
    pars.add_argument("--start_location", type=str, help="Directory to explore")
    pars.add_argument("--config", type=str, help="Config file to use")
    pars.add_argument("--output", type=str, help="Output directory to use")
    pars.add_argument("--file_tree", type=str, help="File tree to use")
    console_log = pars.add_mutually_exclusive_group()
    console_log.add_argument(
        "-v",
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Print info level logging to the console",
    )
    console_log.add_argument(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        default=False,
        help="Print debug level logging to the console",
    )
    pars.add_argument("--use_search_criteria", type=str, default="yes", help="Use search criteria")
    pars.add_argument(
        "--regular_expression_search_criteria",
        type=str,
        default=".*json",
        help="Regular expression search criteria",
    )
    pars.add_argument("-ff", "--filter_files", type=str, default="no", help="Filter files")
    pars.add_argument(
        "-fd", "--filter_directories", type=str, default="no", help="Filter directories"
    )
    pars.add_argument("--filter_hidden", type=str, default="yes", help="Filter hidden")
    pars.add_argument("--filter_list", type=str, default="yes", help="Filter list")
    pars.add_argument(
        "--ignore_list",
        type=str,
        default="code,logs,sourcedata,bids_dataset",
        help="List of files/directories to ignore. Separate names with commas.",
    )
    pars.add_argument("--file_count", type=str, default="yes", help="File count")
    pars.add_argument("--dir_count", type=str, default="no", help="Directory count")
    pars.add_argument("--file_size", type=str, default="yes", help="File size")
    pars.add_argument("--modified_time", type=str, default="no", help="Modified time")
    pars.add_argument("--create_plots", type=str, default="no", help="Create plots")
    pars.add_argument(
        "--number_of_plot_per_measure", type=int, default=6, help="Number of plot per measure"
    )
    pars.add_argument("--print_plots", type=str, default="yes", help="Print plots")
    pars.add_argument("--save_plots", type=str, default="yes", help="Save plots")
    pars.add_argument("--image_path", type=str, default="./results/plots.png", help="Image path")
    pars.add_argument("--create_summary", type=str, default="yes", help="Create summary")
    pars.add_argument(
        "--summary_output_path",
        type=str,
        default="./results/Summary.txt",
        help="Summary output path",
    )
    pars.add_argument("--create_text_tree", type=str, default="yes", help="Create text tree")
    pars.add_argument(
        "--tree_output_path", type=str, default="./results/File_Tree.txt", help="Tree output path"
    )
    pars.add_argument("--create_csv", type=str, default="yes", help="Create csv")
    pars.add_argument(
        "--csv_output_path", type=str, default="./results/Data.csv", help="CSV output path"
    )
    pars.add_argument("--get_configurations", type=str, default="yes", help="Get configurations")
    pars.add_argument("--target_depth ", type=int, default=4, help="Target depth")
    pars.add_argument("--get_depth_range ", type=str, default="yes", help="Get depth range")
    pars.add_argument("--start_depth ", type=int, default=1, help="Start depth")
    pars.add_argument("--end_depth ", type=int, default=5, help="End depth")
    pars.add_argument("--limit_depth ", type=str, default="no", help="Limit depth")
    pars.add_argument("--depth_limit ", type=int, default=4, help="Depth limit")
    pars.add_argument("--file_size_deviation ", type=str, default="yes", help="File size deviation")
    return pars


def _create_logger(
    file_log_path: str, file_log_level: str, is_verbose: bool, is_debug: bool
) -> logging.Logger:
    """Instantiate the logger object that will collect and print logs during the script execution.

    File logging include the date but console logs do not.
    If is_verbose and is_debug are both false, they will be no logs printed to the console.

    Parameters
    ----------
    file_log_path: string
        The path to the file where to save the logs. If is None, will not save path to any files.

    file_log_level: string
        The level of logging for the log file.
        Either "CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG" or "NOTSET".

    is_verbose: bool
        Indicate if the console logger is to be set to the "INFO" level.

    is_debug: bool
        Indicate if the console logger is to be set to the "DEBUG" level
        for more detailed console logs.

    Returns
    -------
    logging.Logger
        The logger object who will redirect the log line given
        during the script execution to the desired outputs.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(file_log_level.upper())
    file_format = logging.Formatter(fmt=LOGGER_FILE_FORMAT, datefmt="%m-%d %H:%M")
    console_format = logging.Formatter(fmt=LOGGER_CONSOLE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_format)
    if is_verbose:
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
    elif is_debug:
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)

    if file_log_path != "None":
        file_handler = logging.FileHandler(file_log_path, mode="w")
        file_handler.setLevel(file_log_level.upper())
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def generate_tree(
    root: str | Path,
    parent: SmartPath | None = None,
    is_last: bool = False,
    criteria: re.Pattern | None = None,
    filter_files: bool = False,
    filter_dir: bool = False,
    filter_hidden: bool = False,
    ignore: list = None,
    depth_limit: int = None,
    file_tree: FileTree = None,
):  # noqa
    """Create a SmartFilePath or SmartDirectoryPath generator object. # noqa: D410 D411 D400

    These generator objects will have to be iterated over
    to get the SmartPath items themselves.
    Returns an iterable of the file structure
    that can be used over each element.
    When a subdirectory is found under the given path,
    will call another instance of this method with it as the root.


    Parameters
    ----------
    root: string or pathlib.Path
        The path for which to generate the SmartPath instance and recursively run
        this function on it's children files
        and directories.

    parent: SmartPath
        The instance of the parent SmartPath.
        This reference allows the children SmartPath to calculate their depth
        relative to the first root of the file structure.

    is_last: bool
        Indicate whether or not this file/directory was the last to be generated
        in it's parent folder.
        Only relevant for visual display of the file structure.

    criteria: re.Pattern
        A regular expression compiled into a Pattern object to be used
        to filter_files and/or directories included
        in the generator output. Files/directories that do not match the regular expression
        will be discarded including all their children regardless of their name for directories.
        If no criteria is given, every file and directory will be included in the generation.

    filter_files: bool
        Whether or not the search criteria will be used to discard files
        whose names do not match the regular expression.

    filter_dir: bool
        Whether or not the search criteria will be used to discard directories
        whose names do not match.

    filter_hidden: bool
        Whether or not to discard hidden files and directories.
        Hidden files and directories are those whose name starts with a dot.

    ignore: list
        A list of file and directory names to ignore.

    depth_limit: int
        The maximum depth to which to generate the file structure relative to the root (level 0).

    file_tree: FileTree
        The FileTree object that will be used to template the file structure and assign
        identities to each file and directory.
    Yields
    ------
    generator object
        Each execution of generate_tree yields a single instance
        of SmartFilePath or SmartDirectoryPath to the generator
        that will create them when iterated upon.
        However, since another generate_tree() function is called on each children found,
        while each function yield a single object,
        the end result will be that a object will be yielded for every file
        and directory found in the initial root (or for every one that matches the criteria).
        Iterating over the output generator object will then allow to act
        on a SmartPath instance of every file and
        directory after only having to call ourself generate_tree() once on the target folder.
    """
    logger = logging.getLogger(LOGGER_NAME)
    root = Path(str(root))

    # Begin by generating the root path
    smart_root = SmartDirectoryPath(
        root,
        parent,
        is_last,
        file_tree,
    )
    yield smart_root
    if depth_limit is not None and smart_root.depth >= depth_limit:
        return
    # Get a list of every file/directory in the root and iterate over them
    if criteria is not None:
        filtered_children = [
            path
            for path in root.iterdir()
            if criteria.match(str(path.name)) is not None
            or (path.is_dir() and not filter_dir)
            or (path.is_file() and not filter_files)
        ]
        children = sorted(filtered_children, key=lambda s: str(s).lower())
    else:
        children = sorted(list(root.iterdir()), key=lambda s: str(s).lower())

    count = 1
    for path in children:
        try:
            # Check if this path is the last children in its parent's directory
            is_last = count == len(children)
            # If the children is a directory, another instance of the method is called and
            # its output is propagated up the generator
            skip = any(path.name == ignore_name for ignore_name in ignore) or (
                path.name.startswith(".") and filter_hidden
            )
            if not skip:
                if path.is_dir():
                    yield from generate_tree(
                        path,
                        parent=smart_root,
                        is_last=is_last,
                        criteria=criteria,
                        filter_files=filter_files,
                        filter_dir=filter_dir,
                        filter_hidden=filter_hidden,
                        ignore=ignore,
                        depth_limit=depth_limit,
                        file_tree=file_tree,
                    )
                # If the children is a file, generate a single instance of SmartPath
                #  associated to its path
                else:
                    yield SmartFilePath(
                        path,
                        smart_root,
                        is_last,
                        file_tree,
                    )
                count += 1

        except FileNotFoundError as e:
            logger.warning("FileNotFoundError", e)
            continue


def generate_tree2(
    root: str | Path,
    criteria: re.Pattern | None = None,
    filter_files: bool = False,
    filter_dir: bool = False,
    filter_hidden: bool = False,
    depth_limit: int = None,
    ignore: list = None,
    file_tree: FileTree = None,
):
    smart_root = SmartDirectoryPath(
        root,
        parent_smart_path=None,
        is_last=False,
        file_tree=file_tree,
    )
    yield from generate_tree2_helper(
        smart_root,
        smart_root.parent,
        smart_root.is_last,
        criteria,
        filter_files,
        filter_dir,
        filter_hidden,
        depth_limit,
        ignore,
        file_tree,
    )


def generate_tree2_helper(
    smart_root: SmartDirectoryPath,
    parent: SmartPath | None = None,
    is_last: bool = False,
    criteria: re.Pattern | None = None,
    filter_files: bool = False,
    filter_dir: bool = False,
    filter_hidden: bool = False,
    depth_limit: int = None,
    ignore: list = None,
    file_tree: FileTree = None,
):
    logger = logging.getLogger(LOGGER_NAME)
    if depth_limit is not None and smart_root.depth >= depth_limit:
        return

    if criteria is not None:
        filtered_children = [
            path
            for path in smart_root.path.iterdir()
            if criteria.match(str(path.name)) is not None
            or (path.is_dir() and not filter_dir)
            or (path.is_file() and not filter_files)
        ]
        children = sorted(filtered_children, key=lambda s: str(s).lower())
    else:
        children = sorted(list(smart_root.path.iterdir()), key=lambda s: str(s).lower())

    count = 1
    for path in children:
        try:
            # Check if this path is the last children in its parent's directory
            is_last = count == len(children)
            # If the children is a directory, another instance of the method is called and
            # its output is propagated up the generator
            skip = any(path.name == ignore_name for ignore_name in ignore) or (
                path.name.startswith(".") and filter_hidden
            )
            if not skip:
                if path.is_dir():
                    smart_child = SmartDirectoryPath(path, smart_root, is_last, file_tree)
                # If the children is a file, generate a single instance of SmartPath
                #  associated to its path
                else:
                    smart_child = SmartFilePath(path, smart_root, is_last, file_tree)
                smart_root.add_children(smart_child)
                count += 1

        except FileNotFoundError as e:
            logger.warning("FileNotFoundError", e)
            continue
    yield smart_root
    for child in smart_root.children:
        try:
            path = child.path
            if path.is_dir():
                yield from generate_tree2_helper(
                    child,
                    parent=smart_root,
                    is_last=is_last,
                    criteria=criteria,
                    filter_files=filter_files,
                    filter_dir=filter_dir,
                    filter_hidden=filter_hidden,
                    ignore=ignore,
                    depth_limit=depth_limit,
                    file_tree=file_tree,
                )
            else:
                yield child
        except FileNotFoundError as e:
            logger.warning("FileNotFoundError", e)
            continue


def get_data_from_paths(
    paths,
    identifier: IdentifierEngine,
    output_path: Path | None = None,
    measures: list[str] = [],
    configuration: Configuration | None = None,
    pipe_file_data: bool = False,
    tree: FileTree | None = None,
) -> tuple[dict, dict]:
    """Iterate over each file/directory in the generator to get measure. # noqa: D410 D411 D400

    Parameters
    ----------
    paths: iterable containing SmartPath objects
        Expected to be the generator object created by generate_tree()
        but can theoretically be any iterable containing SmartPath objects.

    identifier: IdentifierEngine
        Used to extract the identifier of each path to aggregate it
        with similar ones resent in the file structure.
        This IdentifierEngine is also passed to add_configuration
        to allow it to extract identifiers as well. This is mostly deprecated at
        this point.

    output_path: pathlib.Path
        The path to the text file where the file tree output will be saved.
        If none, the type of output is skipped.

    measures: list of string
        The name of the measures to be used in the outputs.
        Each corresponds to a dictionary nested in stat_dict.

    configuration: Configuration
        configuration object that contains the following attributes:
        - target_depth: int passed to add_configuration() to specify which depth of folder.
        - get_configurations: bool passed to add_configuration() to specify whether to get
          the configuration.
        - depth_range: bool passed to add_configuration() to specify whether to use the depth range.
        - start_depth: int passed to add_configuration() to specify the start depth of the range.
        - end_depth: int passed to add_configuration() to specify the end depth of the range.
        - limit_depth: bool passed to add_configuration() to specify whether to use the depth limit.
        - depth_limit: int passed to add_configuration() to limit depth of analysis relative
          to root.

    pipe_file_data: bool
        Whether to output the data from each file found directly
        to the standard output during the execution.
        By default this will print in the console which is not recommended for large dataset.
        If the script is followed by a pipe, this will pass the data to the other script or command.
        Only outputs files because directories shouldn't be relevant for the custom tests.
        Outputted format is  a single string per file in the format:
        'path,identifier,file_size,modified_time'.
        File_size is in bytes, modified_time is in seconds (epoch time).

    tree: FileTree
        The FileTree object used for templating not used currently.
    Returns
    -------
    stat_dict: dict
    The dictionary containing the the values for each measures.

    stat_dict contains nested dictionaries with the following structure:

    .. code-block:: python

        stat_dict={
            'measure1':
                {'identifier1': {
                    'path1': value, 'path2': value, ...},
                'identifier2': {
                    'path3': value, 'path4': value}, ...},
                }
            'measure2':
                {'identifier1': {}, 'identifier2': {}, ...}
            }

    configurations: dict
        Contains the file configurations found for each file/directory identifier
        with the following structure:

        .. code-block:: python

            configurations={
                'identifier1':
                    [ {'structure': ['identifier3', 'identifier4', 'identifier5'],
                                      'paths': ['path1', 'path2']},
                    {'structure': ['identifier3', 'identifier5'], 'paths': ['path4']},
                    ... ]
                'identifier2':
                    [{'structure': [], 'paths': []}, ...]
                }

    """
    configurations = {}
    stat_dict = {measure_name: {} for measure_name in measures}
    if output_path is None:
        for path in paths:
            stat_dict, configurations = data_from_paths_helper(
                path=path,
                identifier=identifier,
                measures=measures,
                configuration=configuration,
                pipe_file_data=pipe_file_data,
                stat_dict=stat_dict,
                configurations=configurations,
                tree=tree,
            )
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            for path in paths:
                stat_dict, configurations = data_from_paths_helper(
                    path=path,
                    identifier=identifier,
                    measures=measures,
                    configuration=configuration,
                    pipe_file_data=pipe_file_data,
                    stat_dict=stat_dict,
                    configurations=configurations,
                    tree=tree,
                )
                f.write(path.displayable(measures=measures, name_max_length=FILENAME_MAX_LENGTH))

    return stat_dict, configurations


def data_from_paths_helper(
    path: SmartPath,
    identifier: IdentifierEngine,
    measures: list[str] = [],
    configuration: Configuration | None = None,
    pipe_file_data: bool = False,
    stat_dict: dict = {},
    configurations: dict = {},
    tree: FileTree | None = None,
) -> tuple[dict, dict]:
    """Must be data from paths helper function.

    Calls add_stats method and add_configuration if specified. Also pipes
    data to standard out if specified.
    """
    identity = path.identifier
    stat_dict = path.add_stats(stat_dict, identity, measures=measures)
    if configuration.get_configurations:
        configurations = add_configuration(
            path,
            configurations,
            identifier,
            target_depth=configuration.target_depth,
            depth_range=configuration.depth_range,
            start_depth=configuration.start_depth,
            end_depth=configuration.end_depth,
            tree=tree,
        )
    if pipe_file_data and isinstance(path, SmartFilePath):
        print(f"{path.path},{path.identifier}," f"{path.file_size},{path.modified_time}")
    return stat_dict, configurations


def add_configuration(
    path: SmartPath,
    configurations: dict,
    identifier: IdentifierEngine,
    target_depth: int | None = None,
    depth_range: bool = False,
    start_depth: int | None = None,
    end_depth: int | None = None,
    tree: FileTree | None = None,
) -> dict:
    """For each directory look at how it's content is structured and save \
       that structure as a configuration.

    Only compare directory of a specific depth relative to the original target directory.
    This prevents computing configurations for folder that aren't relevant
    since we are expecting the repeating
    file structure to have each unit we want to compare at the same depth in the file structure.

    Parameters
    ----------
    path: SmartPath

    configurations: dict
        Contains the file configurations found for each file/directory identifier
        with the following structure:

        .. code-block:: python

                configurations={
                    'identifier1':
                        [ {'structure': ['identifier3', 'identifier4', 'identifier5'],
                                            'paths': ['path1', 'path2']},
                        {'structure': ['identifier3', 'identifier5'], 'paths': ['path4']},
                        ... ]
                    'identifier2':
                        [{'structure': [], 'paths': []}, ...]
                    }

    identifier: IdentifierEngine
        Used to extract the identifier of each path to aggregate it with similar ones resent
        in the file structure. Currently only used for the children in configuration,
        but this it to be updated to use file_tree identifier schema.

    target_depth: int
        The depth at which the repeating directories for which
        to compare their configuration will be.
        Any directory found at a different depth will be ignored by this function.

    depth_range: bool
        Whether to use a depth range to limit the frame of analysis

    start_depth: int
        The start of the depth range.

    end_depth: int
        The end of the depth range.

    Returns
    -------
    configurations: dict
        The updated dict now containing the configuration data \
        from the path that was given as parameter.
    """
    # The root is skipped since it is alone at his target_depth level
    # and thus can't be compared
    # and files are skipped
    if isinstance(path, SmartFilePath) or path.depth == 0:
        return configurations
    # If a target_depth is given, we exclude directories from other depth levels
    """ if tree is not None:
        path_unique_identifier = identifier.get_identifier_tree(path.path, tree)
    else:
        path_unique_identifier = identifier.get_identifier(path.path) """
    path_unique_identifier = path.identifier
    if depth_range and (start_depth is not None and end_depth is not None):
        if path.depth < start_depth or path.depth > end_depth:
            return configurations
    elif target_depth is not None and target_depth >= 0:
        if path.depth != target_depth:
            return configurations

    if path_unique_identifier not in configurations:
        configurations[path_unique_identifier] = []
    children_list = [child.identifier for child in path.children]
    children_list.sort()

    # Compare that organisation with others already found
    # The list of children is the key of the dict and the value
    # is a list of every path with that configuration
    if len(configurations[path_unique_identifier]) == 0:
        # configurations has a list of every configuration associated
        # to every identifier, each element of the list
        # is a dict containing the list of children and the path to all directories
        # following this configuration
        configurations[path_unique_identifier] = [
            {"structure": children_list, "paths": [str(path.path)]}
        ]
    else:
        # Searching if current configuration has already been seen
        for configuration in configurations[path_unique_identifier]:
            if configuration["structure"] == children_list:
                # If the configuration is known, add the current path
                # to the list of that configuration
                configuration["paths"].append(str(path.path))
                return configurations
        # if no match were found, a new configuration is added
        # to the identifier's list of configurations
        configurations[path_unique_identifier].append(
            {"structure": children_list, "paths": [str(path.path)]}
        )

    return configurations


class Output:
    """Helper class for outputs."""

    def __init__(self, config: configparser):
        self.summary = (
            Path(config["Output"]["summary_path"])
            if config["Output"].getboolean("create_summary")
            else None
        )
        self.tree = (
            Path(config["Output"]["text_tree_path"])
            if config["Output"].getboolean("create_text_tree")
            else None
        )
        self.csv = (
            Path(config["Output"]["csv_path"])
            if config["Output"].getboolean("create_csv")
            else None
        )


""


class Configuration2:
    """Helper class for configuration.

    Stores configuration parameters for easier passing to get_data functions.
    """

    def __init__(self, pars: Parser):
        self.get_configurations = pars.get_configurations
        self.target_depth = pars.target_depth
        self.depth_range = pars.use_depth_range
        if self.depth_range:
            self.start_depth = pars.range_start
            self.end_depth = pars.range_end
        else:
            self.start_depth = None
            self.end_depth = None
        self.limit_depth = pars.limit_depth
        self.depth_limit = pars.depth_limit if self.limit_depth else None


class Configuration:
    """Helper class for configuration."""

    def __init__(self, config: configparser):
        self.get_configurations = config["Configurations"].getboolean("get_configurations")
        self.target_depth = config["Configurations"].getint("target_depth")
        self.depth_range = config["Configurations"].getboolean("get_depth_range")
        if self.depth_range:
            self.start_depth = config["Configurations"].getint("start_depth")
            self.end_depth = config["Configurations"].getint("end_depth")
        else:
            self.start_depth = None
            self.end_depth = None
        self.limit_depth = config["Configurations"].getboolean("limit_depth")
        self.depth_limit = (
            config["Configurations"].getint("depth_limit") if self.limit_depth else None
        )


def main2():
    pars = Parser()
    pars = pars.make_parser(Path(CONFIG_PATH))

    if not Path(pars.log_path).exists():
        Path(pars.log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(pars.log_path).touch()

    logger = _create_logger(
        pars.log_path, pars.log_level, is_verbose=pars.verbose, is_debug=pars.debug
    )
    logger.debug("Initializing variables from arguments")

    logger.debug(f"Target directory is : {pars.root_path}")
    # TO_DO make this more rigorously validated
    try:
        tree = FileTree.read(pars.file_tree_path)
    except TypeError:
        print("got here")
        logger.warning(
            f"File tree {pars.file_tree_path} not found, please enter valid path to tree."
        )
        exit(1)
    logger.debug(f"File tree is : {pars.file_tree_path}")

    identifier = IdentifierEngine(pars.regex_file, pars.regex_directory, pars.check_file)

    if pars.use_search:
        try:
            pars.search_expression = re.compile(pars.search_expression)
        except TypeError as e:
            logger.warning(
                f"Search Criteria {pars.search_expression} \
                is invalid, resuming without criteria: {e}"
            )
            pars.search_expression = None

    configuration = Configuration2(pars)

    logger.info(
        f"Output file paths: Summary: {pars.summary_path},\
          Tree: {pars.tree_path},\
            CSV: {pars.csv_path}"
    )
    logger.debug("Launching exploration of target directory.")

    paths = generate_tree2(
        pars.root_path,
        criteria=pars.search_expression,
        filter_files=pars.filter_files,
        filter_dir=pars.filter_directories,
        depth_limit=pars.depth_limit,
        filter_hidden=pars.filter_hidden,
        ignore=pars.filter_custom_list,
        file_tree=tree,
    )

    stat_dict, configurations = get_data_from_paths(
        paths,
        identifier,
        output_path=pars.tree_path,
        measures=pars.measures,
        configuration=configuration,
        pipe_file_data=pars.pipe_data,
        tree=tree,
    )
    logger.info(
        f"Retrieved {len(stat_dict)} measures for "
        f"{len(list(stat_dict.values())[0])} different directory name"
    )
    logger.debug("Creating instance of StatBuilder with the measures")
    stat_builder = StatBuilder(
        stat_dict,
        pars.measures,
        pars.file_size_rounding_percentage,
        pars.modified_time_rounding_margin,
    )

    if pars.create_plots:
        logger.debug("Giving the data to the graphic creator")
        image_path = Path(pars.image_path) if pars.save_plots else None

        stat_builder.create_plots(
            plots_per_measure=pars.num_plots,
            save_path=image_path,
            show_plot=pars.print_plots,
        )
    if pars.summary_path is not None:
        logger.debug("Creating summary")
        with open(pars.summary_path, "w") as f:
            f.write(stat_builder.create_summary(Path(pars.root_path), configurations))
    if pars.csv_path is not None:
        logger.debug("Creating CSV")
        stat_builder.create_csv(pars.csv_path)

    logger.info("Script executed successfully.")


def main():
    """Execute sequence of the script."""
    # Parsing the config file
    config = configparser.ConfigParser()

    # Parsing arguments
    parser = _arg_parser()
    args = parser.parse_args()
    if args.config is not None:
        config.read(Path(args.config))
    else:
        config.read(Path(CONFIG_PATH))
    if not Path(config["Logging"]["log_path"]).exists():
        Path(config["Logging"]["log_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(config["Logging"]["log_path"]).touch()

    # Initializing logger
    logger = _create_logger(
        config["Logging"]["log_path"],
        config["Logging"]["log_level"],
        is_verbose=args.verbose,
        is_debug=args.debug,
    )

    logger.debug("Initializing variables from arguments")

    if args.start_location is not None:
        root = Path(args.start_location)
    else:
        root = Path(config["Input"]["root_path"])
    logger.info(f"Target directory is : {root}")

    if args.file_tree is not None:
        tree = FileTree.read(args.file_tree)
    else:
        cwd = Path.cwd()
        tree = (
            FileTree.read(cwd / config["Input"]["file_tree_path"])
            if config["Input"].getboolean("use_file_tree")
            else None
        )

    logger.debug("Initializing variables from config file")
    identifier = IdentifierEngine(
        config["Categorization"]["regular_expression_file"],
        config["Categorization"]["regular_expression_directory"],
        config["Categorization"].getboolean("check_file"),
    )

    if config["Search_Criteria"].getboolean("use_search_criteria"):
        criteria = config["Search_Criteria"]["regular_expression_search_criteria"]
        filter_files = config["Filter"].getboolean("filter_files")
        filter_dir = config["Filter"].getboolean("filter_directories")

        try:
            criteria = re.compile(criteria)
        except TypeError as e:
            logger.warning(f"Search Criteria {criteria} is invalid, resuming without criteria: {e}")
            criteria = None
    else:
        criteria = None
        filter_files = False
        filter_dir = False

    filter_hidden = config["Filter"].getboolean("filter_hidden")

    if config["Filter"].getboolean("filter_list"):
        ignore = config["Filter"]["ignore_list"].split(",")
    else:
        ignore = []
    output = Output(config)
    configuration = Configuration(config)

    logger.info(
        f"Output file paths: Summary:'{str(output.summary)}', "
        f"Tree:'{str(output.tree)}', CSV:'{str(output.csv)}'"
    )

    logger.debug("Launching exploration of the target directory")
    measure_list = [key for key in config["Measures"] if config["Measures"].getboolean(key)]
    paths = generate_tree(
        root,
        criteria=criteria,
        filter_files=filter_files,
        filter_dir=filter_dir,
        depth_limit=configuration.depth_limit,
        filter_hidden=filter_hidden,
        ignore=ignore,
        file_tree=tree,
    )

    templates = []
    for key in tree.template_keys():
        if tree.get_template(key).parent is not None:
            templates.append(
                (tree.get_template(key).unique_part, tree.get_template(key).parent.unique_part, key)
            )
        else:
            templates.append((tree.get_template(key).unique_part, None, key))
    #    templates = sorted(templates, key=lambda x: len(x[0]), reverse=True)
    stat_dict, configurations = get_data_from_paths(
        paths,
        identifier,
        output_path=output.tree,
        measures=measure_list,
        configuration=configuration,
        pipe_file_data=config["Output.Piping"].getboolean("pipe_data"),
        tree=tree,
        templates=templates,
    )

    logger.info(
        f"Retrieved {len(stat_dict)} measures for "
        f"{len(list(stat_dict.values())[0])} different directory name"
    )
    logger.debug("Creating instance of StatBuilder with the measures")
    size_average = config["Measures_Averaging"].getfloat("size_rounding_percentage")
    time_average = config["Measures_Averaging"].getfloat("time_rounding_seconds")
    stat_builder = StatBuilder(
        stat_dict, measure_list, size_averaging=size_average, time_averaging=time_average
    )

    vis_config = config["Output.Visualization"]
    if vis_config.getboolean("create_plots"):
        logger.debug("Giving the data to the graphic creator")
        if vis_config.getboolean("save_plots"):
            image_path = Path(vis_config["image_path"])
        else:
            image_path = None
        stat_builder.create_plots(
            plots_per_measure=vis_config.getint("number_plot_per_measure"),
            save_path=image_path,
            show_plot=vis_config.getboolean("print_plots"),
        )

    if output.summary is not None:
        logger.debug("Launching summary text output generation.")
        with open(output.summary, "w", encoding="utf-8") as f:
            f.write(stat_builder.create_summary(root, configurations))

    if output.csv is not None:
        logger.debug("Launching CSV output generation.")
        stat_builder.create_csv(output.csv)

    logger.info("Script executed successfully.")


if __name__ == "__main__":
    main2()
