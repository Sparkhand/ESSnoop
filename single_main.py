# Like main but for a single file

import modules.Logger as Logger
import modules.EtherscanDownloader as Downloader
import modules.EtherSolveExecutor as EtherSolve
import modules.JsonAnalyzer as JsonAnalyzer
import pandas as pd
import os

# Clear the log file
with open('logs.txt', 'w'):
    pass
# Create a logger
log = Logger.get_logger(__name__)

# Retrieve EthersScan API key
api_key = os.getenv("ETHERSCAN_API_KEY")

# Check if EtherScan API key is set
if api_key is None:
    print("ERROR! EtherScan API key (ETHERSCAN_API_KEY) is not set")
    log.error("EtherScan API key (ETHERSCAN_API_KEY) is not set")
    exit(1)

# Check if EtherSolve.jar is in the current directory
if not os.path.exists("EtherSolve.jar"):
    print("ERROR! EtherSolve.jar not found in the current directory")
    log.error("EtherSolve.jar not found in the current directory")
    exit(1)

# Check if input_contracts file is in the current directory
if not os.path.exists("input_contracts"):
    print("ERROR! input_contracts file not found in the current directory")
    log.error("input_contracts file not found in the current directory")
    exit(1)

###########################################################
# Download bytecode of contracts
###########################################################
print("Retrieving bytecode of contracts from Etherscan API")

contracts_input_file = "quicktest_input_contracts"
bytecode_output_dir = "quicktest_bytecode"

Downloader.batch_download_bytecode(contracts_input_file, bytecode_output_dir, api_key)

###########################################################
# Compute the .dot files for each contract via EtherSolve
###########################################################
print("Starting EtherSolve analysis for each contract")

json_output_dir = "quicktest_analyzed"

for file in os.listdir(bytecode_output_dir):
    if file.endswith(".bytecode"):
        bytecode_file = os.path.join(bytecode_output_dir, file)
        try:
            EtherSolve.run(bytecode_file, json_output_dir)
        except Exception as e:
            print(f"Error in running EtherSolve for {file}, see logs for details")

###########################################################
# Analyze the .dot files and produce a report (.csv file)
###########################################################

for file in os.listdir(json_output_dir):
    if file.endswith(".json"):
        analyzer = JsonAnalyzer.Analyzer(os.path.join(json_output_dir, file))
        analyzer.analyze()

'''
# Create a Pandas DataFrame to store the report
df = pd.DataFrame(
    columns=[
        "contract",
        "total_jumps",
        "precisely_solved_jumps",
        "soundly_solved_jumps",
        "unreachable_jumps",
    ]
)

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

# Write to a .csv file
report_file = "quicktest_report.csv"
df.to_csv(report_file, index=False)
'''