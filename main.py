import os
import time
import argparse
import pandas as pd
from progress.bar import FillingCirclesBar

import modules.Logger as Logger
import modules.EtherscanDownloader as Downloader
import modules.BytecodeParser as BytecodeParser
import modules.EtherSolveExecutor as EtherSolve
import modules.JsonAnalyzer as JsonAnalyzer

###########################################################
# Utility functions
###########################################################


# Utility function to print an error message
def printError(msg):
    print(f"\033[2;31;43m {msg} \033[0;0m")


def printContractsInvolvedInErrors(contracts: list):
    for contract in contracts:
        printError(f"|- {contract}")


# Utility function to get the total number of opcodes
def get_total_opcodes(filename: str) -> int:
    count = 0
    with open(filename, "r") as file:
        # For each line in the file, check if it contains an opcode
        for line in file:
            line = line.strip()
            if line:
                count += 1
    return count


# Utility function to get the total number of JUMP AND JUMPI statements
def get_total_jumps(filename: str) -> int:
    count = 0
    with open(filename, "r") as file:
        # For each line in the file, check if it contains a JUMP or JUMPI statement
        for line in file:
            line = line.strip()
            if line == "JUMP" or line == "JUMPI":
                count += 1
    return count


def main():
    ###########################################################
    # Parse command line arguments
    ###########################################################
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="main.py",
        description="Analyzes smart contracts using EtherSolve and computes stats on anlysis outcomes",
    )

    parser.add_argument(
        "contracts-filename",
        help="File containing the list of smart contracts to analyze",
    )

    parser.add_argument(
        "-o",
        "--outfile",
        metavar="CSV_OUTFILE",
        help="CSV output filename",
        default="ethersolve_report.csv",
    )

    parser.add_argument(
        "-p",
        "--preserve-output",
        help="Preserve output files (bytecode, opcodes, json)",
        action="store_true",
    )

    ###########################################################
    # Setup
    ###########################################################

    contracts_input_file = vars(parser.parse_args())["contracts-filename"]
    bytecode_output_dir = "bytecode"
    opcodes_output_dir = "opcodes"
    json_output_dir = "analyzed"
    report_file = vars(parser.parse_args())["outfile"]

    # Clear directories
    if not vars(parser.parse_args())["preserve_output"]:
        for directory in [bytecode_output_dir, opcodes_output_dir, json_output_dir]:
            if os.path.exists(directory):
                for filename in os.listdir(directory):
                    os.remove(os.path.join(directory, filename))
                os.rmdir(directory)

    # Clear the log file
    with open("logs.txt", "w"):
        pass
    # Create a logger
    log = Logger.get_logger(__name__)

    # Retrieve EthersScan API key
    api_key = os.getenv("ETHERSCAN_API_KEY")

    # Check if EtherScan API key is set
    if api_key is None:
        printError("ERROR! EtherScan API key (ETHERSCAN_API_KEY) is not set")
        log.error("EtherScan API key (ETHERSCAN_API_KEY) is not set")
        exit(1)

    # Check if EtherSolve.jar is in the current directory
    if not os.path.exists("EtherSolve.jar"):
        printError("ERROR! EtherSolve.jar not found in the current directory")
        log.error("EtherSolve.jar not found in the current directory")
        exit(1)

    # Check if input_contracts file is in the current directory
    if not os.path.exists(contracts_input_file):
        printError(
            f"ERROR! {contracts_input_file} file not found in the current directory"
        )
        log.error(f"{contracts_input_file} file not found in the current directory")
        exit(1)

    # Retrieve a list of contract addresses from the input file
    contract_addresses: set = set()
    with open(contracts_input_file, "r") as file:
        for line in file:
            contract = line.strip()
            contract_addresses.add(contract)

    ###########################################################
    # Download bytecode of contracts
    ###########################################################

    # Check if the bytecode output dir exists
    if not os.path.exists(bytecode_output_dir):
        os.makedirs(bytecode_output_dir)

    pbar = FillingCirclesBar(
        "Downloading bytecode",
        max=len(contract_addresses),
        suffix="%(percent)d%% [%(index)d / %(max)d]",
    )

    ended_with_error = False
    involved_in_error: set = set()

    # Download each contract
    count = 0
    for contract in contract_addresses:
        try:
            Downloader.download_bytecode(bytecode_output_dir, contract, api_key)
        except Exception:
            involved_in_error.add(contract)
            ended_with_error = True
        finally:
            pbar.next()
        count += 1
        if count % 5 == 0:
            time.sleep(0.01)
    pbar.finish()

    # Check for errors
    if ended_with_error:
        printError(
            "Errors occurred during bytecode downloading, check the logs for more info"
        )
        printError(f"Contracts involved in errors:")
        printContractsInvolvedInErrors(involved_in_error)
        contract_addresses.difference_update(set(involved_in_error))

    ###########################################################
    # Parse the bytecode and extract opcodes
    ###########################################################

    # Check if the output dir exists
    if not os.path.exists(opcodes_output_dir):
        os.makedirs(opcodes_output_dir)

    pbar = FillingCirclesBar(
        "Parsing bytecode",
        max=len(contract_addresses),
        suffix="%(percent)d%% [%(index)d / %(max)d]",
    )

    ended_with_error = False
    involved_in_error: set = set()

    for contract in contract_addresses:
        try:
            bytecode_file = os.path.join(bytecode_output_dir, f"{contract}.bytecode")
            BytecodeParser.parseBytecode(
                bytecode_file,
                opcodes_output_dir,
            )
        except Exception:
            ended_with_error = True
            involved_in_error.add(contract)
        finally:
            pbar.next()
    pbar.finish()

    # Check for errors
    if ended_with_error:
        printError(
            "Errors occurred during bytecode parsing, check the logs for more info"
        )
        printError(f"Contracts involved in errors:")
        printContractsInvolvedInErrors(involved_in_error)
        contract_addresses.difference_update(set(involved_in_error))

    ###########################################################
    # Compute the JSON files for each contract via EtherSolve
    ###########################################################

    # Check if the output dir exists
    if not os.path.exists(json_output_dir):
        os.makedirs(json_output_dir)

    ended_with_error = False
    involved_in_error: set = set()

    pbar = FillingCirclesBar(
        "Executing EtherSolve",
        max=len(contract_addresses),
        suffix="%(percent)d%% [%(index)d / %(max)d]",
    )

    # Run EtherSolve
    for contract in contract_addresses:
        bytecode_file = os.path.join(bytecode_output_dir, f"{contract}.bytecode")
        try:
            EtherSolve.run(bytecode_file, json_output_dir)
        except Exception:
            ended_with_error = True
            involved_in_error.add(contract)
        finally:
            pbar.next()
    pbar.finish()

    # Check for errors
    if ended_with_error:
        printError(
            "Errors occurred during EtherSolve analysis, check the logs for more info"
        )
        printError(f"Contracts involved in errors:")
        printContractsInvolvedInErrors(involved_in_error)
        contract_addresses.difference_update(set(involved_in_error))

    ###########################################################
    # Analyze the JSON files and retrieve stats, then add them to a Pandas DataFrame
    ###########################################################

    dataframe = pd.DataFrame(
        columns=[
            "Smart Contract",
            "Total Opcodes",
            "Total Jumps",
            "Solved Jumps" "Not Solved Jumps",
        ]
    )

    pbar = FillingCirclesBar(
        "Analyzing JSON files",
        max=len(contract_addresses),
        suffix="%(percent)d%% [%(index)d / %(max)d]",
    )

    ended_with_error = False
    involved_in_error: set = set()

    for contract in contract_addresses:
        # Retrieve opcodes and total jumps from the opcodes file
        opcodes_file = os.path.join(opcodes_output_dir, f"{contract}.opcodes")

        if not os.path.exists(opcodes_file):
            log.error(f"Opcodes file {opcodes_file} not found")
            continue

        total_opcodes = get_total_opcodes(opcodes_file)
        total_jumps = get_total_jumps(opcodes_file)

        # Then, analyze the JSON file
        json_stats = {}

        json_file = os.path.join(json_output_dir, f"{contract}.json")
        analyzer = JsonAnalyzer.Analyzer(json_file)

        try:
            json_stats = analyzer.analyze()
        except Exception:
            ended_with_error = True
            involved_in_error.add(contract)
            continue
        finally:
            del analyzer  # Free resources

        # Compute stats as per dataframe columns
        smart_contract = contract
        solved_jumps = (
            json_stats["precisely_solved_jumps"]
            + json_stats["soundly_solved_jumps"]
        )
        not_solved_jumps = total_jumps - solved_jumps

        # Add the stats to the DataFrame
        to_insert: pd.DataFrame = pd.DataFrame(
            [
                {
                    "Smart Contract": smart_contract,
                    "Total Opcodes": total_opcodes,
                    "Total Jumps": total_jumps,
                    "Solved Jumps": solved_jumps,
                    "Not Solved Jumps": not_solved_jumps,
                }
            ]
        )

        if dataframe.empty:
            dataframe = to_insert
        else:
            dataframe = pd.concat([dataframe, to_insert])

        pbar.next()

    pbar.finish()

    # Check for errors
    if ended_with_error:
        printError("Errors occurred during JSON analysis, check the logs for more info")
        printError(f"Contracts involved in errors:")
        printContractsInvolvedInErrors(involved_in_error)
        contract_addresses.difference_update(set(involved_in_error))

    ###########################################################
    # Write the DataFrame to a .csv file, and analyze the data with Pandas
    ###########################################################

    # Write the DataFrame to a .csv file
    print(f"Writing report to {report_file}... ", end="")
    dataframe.to_csv(report_file, index=False)
    print("Done!")


if __name__ == "__main__":
    main()
