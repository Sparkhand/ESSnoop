import os
import time
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


###########################################################
# Setup
###########################################################

contracts_input_file = "input_contracts"
bytecode_output_dir = "bytecode"
opcodes_output_dir = "opcodes"
json_output_dir = "analyzed"
report_file = "report.csv"

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
    printError(f"ERROR! {contracts_input_file} file not found in the current directory")
    log.error(f"{contracts_input_file} file not found in the current directory")
    exit(1)

###########################################################
# Download bytecode of contracts
###########################################################

# Check if the output dir exists
if not os.path.exists(bytecode_output_dir):
    os.makedirs(bytecode_output_dir)

total_lines = sum(1 for line in open(contracts_input_file))
pbar = FillingCirclesBar(
    "Downloading bytecode",
    max=total_lines,
    suffix="%(percent)d%% [%(index)d / %(max)d]",
)

ended_with_error = False
involved_in_error = []

# For each line in the input file, download the bytecode of the contract
with open(contracts_input_file, "r") as file:
    count = 0
    for line in file:
        contract_address = line.strip()

        try:
            Downloader.download_bytecode(bytecode_output_dir, contract_address, api_key)
        except Exception as e:
            log.error(str(e))
            ended_with_error = True
            involved_in_error.append(contract_address)
        pbar.next()

        # Pause every 5 requests to avoid rate limiting
        count += 1
        if count % 5 == 0:
            time.sleep(0.005)
pbar.finish()

# Check for errors
if ended_with_error:
    printError(
        "Errors occurred during bytecode downloading, check the logs for more info"
    )
    printError(f"!# Contracts involved in errors: {involved_in_error}")

###########################################################
# Parse the bytecode and extract opcodes
###########################################################

# Check if the output dir exists
if not os.path.exists(opcodes_output_dir):
    os.makedirs(opcodes_output_dir)

total_to_parse = len(os.listdir(bytecode_output_dir))
pbar = FillingCirclesBar(
    "Parsing bytecode",
    max=total_to_parse,
    suffix="%(percent)d%% [%(index)d / %(max)d]",
)

ended_with_error = False
involved_in_error = []

for file in os.listdir(bytecode_output_dir):
    if file.endswith(".bytecode"):
        bytecode_file = os.path.join(bytecode_output_dir, file)
        try:
            BytecodeParser.parseBytecode(bytecode_file, opcodes_output_dir)
        except Exception as e:
            log.error(str(e))
            ended_with_error = True
            involved_in_error.append(os.path.basename(bytecode_file).split(".")[0])
        pbar.next()
pbar.finish()

# Check for errors
if ended_with_error:
    printError("Errors occurred during bytecode parsing, check the logs for more info")
    printError(f"Contracts involved in errors: {involved_in_error}")

###########################################################
# Compute the JSON files for each contract via EtherSolve
###########################################################

# Check if the output dir exists
if not os.path.exists(json_output_dir):
    os.makedirs(json_output_dir)

total_downloaded = len(os.listdir(bytecode_output_dir))
ended_with_error = False
involved_in_error = []

pbar = FillingCirclesBar(
    "Executing EtherSolve",
    max=total_downloaded,
    suffix="%(percent)d%% [%(index)d / %(max)d]",
)
for file in os.listdir(bytecode_output_dir):
    if file.endswith(".bytecode"):
        bytecode_file = os.path.join(bytecode_output_dir, file)
        try:
            EtherSolve.run(bytecode_file, json_output_dir)
        except Exception as e:
            log.error(str(e))
            ended_with_error = True
            involved_in_error.append(os.path.basename(bytecode_file).split(".")[0])
        pbar.next()
pbar.finish()

# Check for errors
if ended_with_error:
    printError(
        "Errors occurred during EtherSolve analysis, check the logs for more info"
    )
    printError(f"Contracts involved in errors: {involved_in_error}")

###########################################################
# Analyze the JSON files and retrieve stats, then add them to a Pandas DataFrame
# and finally write the DataFrame to a .csv file
###########################################################

dataframe = pd.DataFrame(
    columns=[
        "contract",
        "total_jumps",
        "precisely_solved_jumps",
        "soundly_solved_jumps",
        "unreachable_jumps",
        "unsolved_jumps",
    ]
)

pbar = FillingCirclesBar(
    "Analyzing JSON files",
    max=len(os.listdir(json_output_dir)),
    suffix="%(percent)d%% [%(index)d / %(max)d]",
)

ended_with_error = False
involved_in_error = []

for file in os.listdir(json_output_dir):
    if file.endswith(".json"):
        # First, retrieve the total number of JUMP and JUMPI statements from
        # the .opcodes file
        opcodes_file = os.path.join(opcodes_output_dir, file.split(".")[0] + ".opcodes")
        if not os.path.exists(opcodes_file):
            log.error(f"Opcodes file {opcodes_file} not found")
            continue
        total_jumps = get_total_jumps(opcodes_file)

        # Then, analyze the JSON file
        json_stats = {}

        analyzer = JsonAnalyzer.Analyzer(os.path.join(json_output_dir, file))
        try:
            json_stats = analyzer.analyze()
        except Exception as e:
            log.error(str(e))
            ended_with_error = True
            involved_in_error.append(os.path.basename(file).split(".")[0])
            continue

        # Add the stats to the DataFrame
        dataframe = pd.concat(
            [
                dataframe,
                pd.DataFrame(
                    [
                        {
                            "contract": os.path.basename(file).split(".")[0],
                            "total_jumps": total_jumps,
                            **json_stats,
                        }
                    ]
                ),
            ]
        )

        pbar.next()

pbar.finish()

# Check for errors
if ended_with_error:
    printError("Errors occurred during JSON analysis, check the logs for more info")
    printError(f"Contracts involved in errors: {involved_in_error}")

# Write the DataFrame to a .csv file
print(f"Writing report to {report_file}... ", end="")
dataframe.to_csv(report_file, index=False)
print("Done!")

"""
for file in os.listdir(json_output_dir):
    metrics = {
        "total_jumps": -1,
        "precisely_solved_jumps": -1,
        "soundly_solved_jumps": -1,
        "unreachable_jumps": -1,
    }
    if file.endswith(".dot"):
        dot_file = os.path.join(json_output_dir, file)
        try:
            print(f"Analyzing graph of {file}")
            metrics = DotAnalyzer.analyze(dot_file)
        except Exception as e:
            print(e)

        # Calculate solved_percentage as:
        # (precisely_solved_jumps + soundly_solved_jumps) / (total_jumps - unreachable_jumps)
        try:
            solved_percentage = (
                metrics["precisely_solved_jumps"] + metrics["soundly_solved_jumps"]
            ) / (metrics["total_jumps"] - metrics["unreachable_jumps"])
        except ZeroDivisionError:
            solved_percentage = -1

        if solved_percentage < 0:
            solved_percentage = -1

        df = pd.concat(
            [df, pd.DataFrame([{"contract": file.split(".")[0], **metrics, "solved_percentage": solved_percentage}])]
        )
"""
