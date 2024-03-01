"""Main script

This script orchestrates the whole pipeline to fetch smart contracts
from Etherscan, analyze them using EtherSolve and analyze the JSON
output of each analysis to compute stats about solved jumps.
"""


import argparse
import os
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from functools import partial

import pandas as pd
from progress.bar import FillingCirclesBar
from ratemate import RateLimit

import modules.logger as logger
from modules.etherscandownloader import download_bytecode
from modules.ethersolverunner import run_ethersolve
from modules.jsonanalyzer import analyze as analyze_json
from modules.opcodesparser import parse_bytecode

# region Global variables

log: logger.logging.Logger

# endregion

# region Argument Parser


def get_parser() -> argparse.ArgumentParser:
    """A function that returns a tailored argument parser for this
    script.

    Returns:
        argparse.ArgumentParser: the argument parser.
    """

    # Parser init
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="essnoop.py",
        description="ESSnoop - EtherSolve Snoop | Analyzes smart "
                    "contracts using EtherSolve and computes stats on "
                    "analysis outcomes.",
    )

    # Input filename (positional)
    parser.add_argument(
        "input-filename",
        help="File containing the list of smart contracts to analyze.",
    )

    # Report output filename (optional)
    parser.add_argument(
        "-o",
        "--csv-outfile",
        metavar="CSV_OUTFILE",
        help="CSV output filename.",
        default="ethersolve_report.csv",
    )

    # Preserve bytecode output (optional)
    parser.add_argument(
        "-b",
        "--preserve-bytecode",
        help="Preserve downloaded bytecode so it doesn't have to be "
             "downloaded again.",
        action="store_true",
    )

    # Preserve opcodes output (optional)
    parser.add_argument(
        "-p",
        "--preserve-all",
        help="Preserve all output directories and files (bytecode, "
             "opcodes, json). It overrides -b flag.",
        action="store_true",
    )

    # Etherscan API key (optional)
    parser.add_argument(
        "-k",
        "--etherscan-api-key",
        metavar="ETHERSCAN_API_KEY",
        help="Specifiy your Etherscan API key. This is useful if you "
             "haven't set ETHERSCAN_API_KEY environment variable.",
        action="store",
        default=None,
    )

    # EtherSolve Jar name (optional)
    parser.add_argument(
        "-j",
        "--ethersolve-jar",
        metavar="ETHERSOLVE_JAR",
        help="Specify the name of the EtherSolve jar file (include .jar).",
        action="store",
        default="EtherSolve.jar",
    )

    return parser


# endregion

# region Helper functions

def clear_output_dirs(dirs: list[str]) -> None:
    """A function that clears the specifies directories by deleting
    all the files inside them first and then deleting the directories
    themselves.

    Args:
        dirs (list): a list of the directories to be cleared.
    """

    for dir in dirs:
        if os.path.exists(dir):
            for f in os.listdir(dir):
                os.remove(os.path.join(dir, f))
            os.rmdir(dir)


def log_init(logfile: str) -> logger.logging.Logger:
    """A function to initialize the logger for this script. It makes
    sure the log file is cleared before each run.

    Args:
        logfile (str): the filename of the log file.

    Returns:
        logger.logging.Logger: the logger instance.
    """

    # Clear the log file
    with open(logfile, "w"):
        pass

    return logger.get_logger(__name__, logfile)


def get_pbar(msg: str, count: int) -> FillingCirclesBar:
    """A function that returns a FillingCirclesBar instance customized
    to show the progress of the script in terms of percentage and
    done / total. A custom message can be passed as an argument as well
    as the count of total elements.

    Args:
        msg (str): a custom message which is shown in the progress bar.
        count (int): the total number of elements to be processed.

    Returns:
        FillingCirclesBar: a tailored instance of FillingCirclesBar.
    """
    return FillingCirclesBar(
        msg,
        max=count,
        suffix="%(percent)d%% [%(index)d / %(max)d]",
    )


def print_error(msg: str) -> None:
    """A simple utility function which prints an error message to
    stdout using red text over a yellow background.

    Args:
        msg (str): the message to be printed.
    """
    print(f"\033[2;31;43m{msg}\033[0;0m")


def report_errors(msg: str, involved: set[str]) -> None:
    """Prints the list of smart contracts involved in errors, using
    a specific format specified by `print_error` function.

    Args:
        msg (str): the opening message to be printed.
        involved (set): a set of smart contracts involved in errors.
    """

    print_error(msg)
    for contract in involved:
        print_error(f"|- {contract}")
    print_error("Please check the log file for more details.")


def check_input_file_exists(infile: str) -> None:
    """Checks that the input file specified by the user exists.

    Args:
        filename (str): the input file to be checked.
    """

    if not os.path.exists(infile):
        print_error(f"ERROR! Input file {infile} file not found in the current "
                    "directory")
        global log
        log.error(f"Input file {infile} not found current directory")
        exit(1)


def check_ethersolve_jar_exists(jarfile: str) -> None:
    """Checks that the specified EtherSolve jar file exists.

    Args:
        jarname (str): the EtherSolve jar file to be checked.
    """

    if not os.path.exists(jarfile):
        print_error(f"ERROR! {jarfile} not found in the current "
                    "directory")
        global log
        log.error(f"{jarfile} not found in the current directory")
        exit(1)


def retrieve_api_key(actual_key: str) -> str:
    """Attempts a retrieval of the EtherScan API key from either the
    passed argument or the environment variable. It stops the script
    if the key is not found.

    Args:
        actual_key (str): the key passed as a CLI argument.

    Returns:
        str: the retrieved key.
    """

    api_key: str | None

    if actual_key is None:  # -> wasn't passed as argument
        api_key = os.getenv("ETHERSCAN_API_KEY")
        if api_key is None:  # -> not set as environment variable
            print_error("ERROR! EtherScan API key wasn't passed as an "
                        "argument nor is set as environment variable "
                        "(ETHERSCAN_API_KEY)")
            global log
            log.error("EtherScan API key (ETHERSCAN_API_KEY) is not set")
            exit(1)

    return api_key


def get_sc_addresses(infile: str) -> set[str]:
    """Retrieves a set of smart contract addresses from the specified
    input file. If a contract address is duplicated, a warning is
    printed to the log file.

    Args:
        infile (str): the input file with a list of smart contract
                      addresses.

    Returns:
        set[str]: the set of smart contract addresses.
    """

    contract_addresses: set = set()

    with open(infile, "r") as file:
        for line in file:
            contract = line.strip()

            if contract in contract_addresses:
                global log
                log.warning(f"Contract address {contract} is duplicated "
                            "in the input file")

            contract_addresses.add(contract)

    return contract_addresses


# endregion

# region Schedulers

def download_bytecode_scheduler(addresses: set[str], api_key: str,
                                output_dir: str, logfile: str) -> set[str]:
    """A scheduler which downloads bytecode for the specified
    smart contract addresses. It uses the `download_bytecode` function
    from the `etherscandownloader` module. It uses multiprocessing
    through the `ProcessPoolExecutor` class to parallelize the download
    while respecting the rate limit using the `RateLimit` class.

    Args:
        addresses (set[str]): a list of smart contract addresses
                              to download.
        api_key (str): the Etherscan API key.
        output_dir (str): the output directory for the downloaded files.
        logfile (str): the filename of the log file.

    Returns:
        set[str]: the set of smart contract addresses that failed
                  to download.
    """

    # Set up logger
    log: logger.logging.Logger = logger.get_logger("Etherscan Downloader",
                                                   filename=logfile)

    # Create output dir if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # A set of addresses that failed to download
    involved_in_error: set = set()

    # Configure worker
    worker: partial = partial(download_bytecode, output_dir=output_dir,
                              api_key=api_key, log=log)

    # Custom progress bar, rate limiter and callback
    pbar: FillingCirclesBar = get_pbar("Downloading bytecode", len(addresses))

    rate_limit: RateLimit = RateLimit(3, 2)

    def callback(_):
        pbar.next()

    # Do work
    futures: list[Future] = []

    with ProcessPoolExecutor() as executor:
        for address in addresses:
            rate_limit.wait()
            future: Future = executor.submit(worker, address)
            future.add_done_callback(callback)
            futures.append(future)

        for completed in as_completed(futures):
            result: str | None = completed.result()
            if result is not None:
                involved_in_error.add(result)

    pbar.finish()

    return involved_in_error


def parse_opcodes_scheduler(addresses: set[str], input_dir: str,
                            output_dir: str, logfile: str) -> set[str]:
    """A scheduler which parses the opcodes for the specified smart
    contract addresses .bytecode files. It uses the `parse_bytecode`
    function from the `opcodesparser` module. It uses multiprocessing
    through the `ProcessPoolExecutor` class to parallelize the parsing.

    Args:
        addresses (set): a set of smart contract addresses.
        input_dir (str): the input directory with the .bytecode files.
        output_dir (str): an output directory for the parsed opcodes
                          .opcodes files.
        logfile (str): the filename of the log file.

    Returns:
        set: a set of smart contract addresses for which the opcodes
             could not be parsed.
    """

    # Set up logger
    log: logger.logging.Logger = logger.get_logger("Opcodes Parser",
                                                   filename=logfile)

    # Create output dir if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # A set of addresses that failed to download
    involved_in_error: set = set()

    # Configure worker
    worker: partial = partial(parse_bytecode, input_dir=input_dir,
                              output_dir=output_dir, log=log)

    # Custom progress bar and callback
    pbar: FillingCirclesBar = get_pbar("Parsing opcodes", len(addresses))

    def callback(_):
        pbar.next()

    # Do work
    futures: list[Future] = []

    with ProcessPoolExecutor() as executor:
        for address in addresses:
            future: Future = executor.submit(worker, address)
            future.add_done_callback(callback)
            futures.append(future)

        for completed in as_completed(futures):
            result: str | None = completed.result()
            if result is not None:
                involved_in_error.add(result)

    pbar.finish()

    return involved_in_error


def ethersolve_runner_scheduler(addresses: set[str], jarfile: str,
                                input_dir: str, output_dir: str,
                                logfile: str) -> set[str]:
    """A scheduler which runs the EtherSolve tool on the specified
    smart contract addresses (on their .bytecode files). It uses the
    `run_ethersolve` function from the `ethersolverunner` module. It
    uses multiprocessing through the `ProcessPoolExecutor` class to
    parallelize the execution for each input.

    Args:
        addresses (set[str]): a set of smart contract addresses.
        jarfile (str): the path to the EtherSolve jar file.
        input_dir (str): the input directory with the .bytecode files.
        output_dir (str): the output directory with the execution
                          outputs in .json format.
        logfile (str): the filename of the log file.

    Returns:
        set[str]: a set of smart contract addresses for which the
                 execution of EtherSolve failed.
    """

    # Set up logger
    log: logger.logging.Logger = logger.get_logger("EtherSolve Runner",
                                                   filename=logfile)

    # Create output dir if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # A set of addresses that failed to download
    involved_in_error: set = set()

    # Configure worker
    worker: partial = partial(run_ethersolve, jarfile=jarfile,
                              input_dir=input_dir, output_dir=output_dir,
                              log=log)

    # Custom progress bar and callback
    pbar: FillingCirclesBar = get_pbar("Running EtherSolve", len(addresses))

    def callback(_):
        pbar.next()

    # Do work
    futures: list[Future] = []

    with ProcessPoolExecutor() as executor:
        for address in addresses:
            future: Future = executor.submit(worker, address)
            future.add_done_callback(callback)
            futures.append(future)

        for completed in as_completed(futures):
            result: str | None = completed.result()
            if result is not None:
                involved_in_error.add(result)

    pbar.finish()

    return involved_in_error


def json_analyzer_scheduler(addresses: set, opcodes_dir: str, json_dir: str,
                            logfile: str) -> tuple[pd.DataFrame, set[str]]:
    """A scheduler which analyzes the JSON files produced by EtherSolve
    analysis on the specified smart contract addresses. It uses the
    `analyze_json` function from the `jsonanalyzer` module. It uses
    multiprocessing through the `ProcessPoolExecutor` class to
    parallelize the execution for each input. Stats are packed in a
    `Pandas` `DataFrame`.

    Args:
        addresses (set): a set of smart contract addresses.
        opcodes_dir (str): the directory with the .opcodes files.
        json_dir (str): the directory with the .json files.
        logfile (str): the filename of the log file.

    Returns:
        tuple[pd.DataFrame, set[str]]: a tuple with a Pandas DataFrame
                                       containing the computed stats,
                                       and a set of smart contract
                                       addresses for which the JSON
                                       analysis encountered errors.
                                       These contracts will be included
                                       in the DataFrame.
    """

    # Set up logger
    log: logger.logging.Logger = logger.get_logger("JSON Analyzer",
                                                   filename=logfile)

    # A set of addresses that failed to download
    involved_in_error: set = set()

    # A DataFrame with the retrieved stats
    df_res: pd.DataFrame = pd.DataFrame()

    # Configure worker
    worker: partial = partial(analyze_json, opcodes_dir=opcodes_dir,
                              json_dir=json_dir, log=log)

    # Custom progress bar and callback
    pbar: FillingCirclesBar = get_pbar("Analyzing JSON", len(addresses))

    def callback(_):
        pbar.next()

    # Do work
    futures: list[Future] = []

    with ProcessPoolExecutor() as executor:
        for address in addresses:
            future: Future = executor.submit(worker, address)
            future.add_done_callback(callback)
            futures.append(future)

        for completed in as_completed(futures):
            STATS: dict
            ADDRESS: str | None

            STATS, ADDRESS = completed.result()

            if ADDRESS is not None:
                involved_in_error.add(ADDRESS)

            # Add the stats to the DataFrame
            to_insert: pd.DataFrame = pd.DataFrame([STATS])

            if df_res.empty:
                df_res = to_insert
            else:
                df_res = pd.concat([df_res, to_insert], ignore_index=True)

    pbar.finish()

    return (df_res, involved_in_error)


# endregion

# region Main


def main() -> None:
    # Definition of paths
    PATHS: dict = {
        "contracts_input_file": "",
        "bytecode_output_dir": "bytecode",
        "opcodes_output_dir": "opcodes",
        "json_output_dir": "analyzed",
        "report_output_file": "",
        "log_output_file": "logfile.log",
    }

    # CLI arguments parsing
    parser: argparse.ArgumentParser = get_parser()
    args: dict = vars(parser.parse_args())

    PATHS["contracts_input_file"] = args["input-filename"]
    PATHS["report_output_file"] = args["csv_outfile"]

    ETHERSCAN_API_KEY = args["etherscan_api_key"]
    ETHERSOLVE_JAR = args["ethersolve_jar"]

    PRESERVE_ALL: bool = args["preserve_all"]
    PRESERVE_BYTECODE: bool = args["preserve_bytecode"] | PRESERVE_ALL

    # Clear output directories
    if not PRESERVE_ALL:
        to_delete: list = [
            PATHS["opcodes_output_dir"],
            PATHS["json_output_dir"],
        ]

        if not PRESERVE_BYTECODE:
            to_delete.append(PATHS["bytecode_output_dir"])

        clear_output_dirs(to_delete)

    # Init logs
    global log
    log = log_init(PATHS["log_output_file"])

    # Check if the input file specified by the user exists
    check_input_file_exists(PATHS["contracts_input_file"])

    # Check if EtherSolve.jar is in the current directory
    check_ethersolve_jar_exists(ETHERSOLVE_JAR)

    # Retrieve Etherscan API key
    ETHERSCAN_API_KEY = retrieve_api_key(ETHERSCAN_API_KEY)

    # Retrieve the set of contract addresses from the input file
    sc_addresses: set = get_sc_addresses(PATHS["contracts_input_file"])

    # Download the bytecode of each smart contract
    if not PRESERVE_BYTECODE:
        ERRORS: set = download_bytecode_scheduler(sc_addresses,
                                                  ETHERSCAN_API_KEY,
                                                  PATHS["bytecode_output_dir"],
                                                  PATHS["log_output_file"])

        if len(ERRORS) != 0:
            report_errors("Bytecode download failed for the following "
                          "contracts:",
                          ERRORS)

            sc_addresses.difference_update(ERRORS)

            print(f"\nScript will go on with {len(sc_addresses)} "
                  "smart contracts\n")
    else:
        print("Bytecode download skipped")
        log.info("Bytecode download skipped")

    # Parse the bytecode to extract opcodes
    if not PRESERVE_ALL:
        ERRORS: set = parse_opcodes_scheduler(sc_addresses,
                                              PATHS["bytecode_output_dir"],
                                              PATHS["opcodes_output_dir"],
                                              PATHS["log_output_file"])

        if len(ERRORS) != 0:
            report_errors("Opcodes parsing failed for the following "
                          "contracts:",
                          ERRORS)

            sc_addresses.difference_update(ERRORS)

            print(f"\nScript will go on with {len(sc_addresses)} "
                  "smart contracts\n")
    else:
        print("Opcodes parsing skipped")
        log.info("Opcodes parsing skipped")

    # Run EtherSolve on each smart contract
    if not PRESERVE_ALL:
        ERRORS: set = ethersolve_runner_scheduler(sc_addresses,
                                                  ETHERSOLVE_JAR,
                                                  PATHS["bytecode_output_dir"],
                                                  PATHS["json_output_dir"],
                                                  PATHS["log_output_file"])

        if len(ERRORS) != 0:
            report_errors("EtherSolve execution failed for the following "
                          "contracts:",
                          ERRORS)

            sc_addresses.difference_update(ERRORS)

            print(f"\nScript will go on with {len(sc_addresses)} "
                  "smart contracts\n")
    else:
        print("EtherSolve execution skipped")
        log.info("EtherSolve execution skipped")

    # Analyze EtherScan JSON output for each smart contract
    STATS_DF: pd.DataFrame
    ERRORS: set

    STATS_DF, ERRORS = json_analyzer_scheduler(sc_addresses,
                                               PATHS["opcodes_output_dir"],
                                               PATHS["json_output_dir"],
                                               PATHS["log_output_file"])

    if len(ERRORS) != 0:
        report_errors("JSON analysis encountered mistakes for the following "
                      "contracts (they are included in the report):",
                      ERRORS)

    # Export the report to a CSV file
    STATS_DF.to_csv(PATHS["report_output_file"], index=False)

    print("Report written to", PATHS["report_output_file"])
    log.info("Report written to %s", PATHS["report_output_file"])


if __name__ == "__main__":
    main()


# endregion
