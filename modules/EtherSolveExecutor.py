###########################################################
# Python to run EtherSolve.jar given the file containing the bytecode
# of the contract and the output directory.
###########################################################

import modules.Logger as Logger
from subprocess import Popen, PIPE
import os

# Logger
log = Logger.get_logger(__name__)


# Run EtherSolve.jar
def run(bytecode_file: str, output_dir: str):
    # Check if the output dir exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Extract filename without extension and parent directory
    result_filename = os.path.basename(bytecode_file).split(".")[0]

    log.info(f"Launching EtherSolve analysis for {bytecode_file}")

    # Run EtherSolve.jar
    command = [
        "java",
        "-jar",
        "EtherSolve.jar",
        "-rj",
        bytecode_file,
        "-o",
        f"{output_dir}/{result_filename}.json",
    ]
    proc = Popen(command, stdout=PIPE, stderr=PIPE)
    proc.wait()
    
    # Check if the .json file has been created
    if not os.path.exists(f"{output_dir}/{result_filename}.json"):
        log.error(
            f"Error in running EtherSolve for {bytecode_file}, reason:\n {proc.stderr.read().decode('utf-8')}"
        )
        raise Exception()
    else:
        log.info(f"Analysis for {bytecode_file} completed successfully")
