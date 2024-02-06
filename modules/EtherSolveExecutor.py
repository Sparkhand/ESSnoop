###########################################################
# Python module to run EtherSolve.jar given the file containing the bytecode
# of the contract and the output directory.
###########################################################

import modules.Logger as Logger
from subprocess import Popen, PIPE
import os

# Logger
log = Logger.get_logger(__name__)


# Run EtherSolve.jar
def run(bytecode_file: str, output_dir: str):
    # Extract filename without extension and parent directory
    result_filename = os.path.basename(bytecode_file).split(".")[0]

    log.info(f"Launching EtherSolve analysis for {result_filename}")

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

    # Log stdout if not empty
    if proc.stdout.read().decode("utf-8"):
        log.info(proc.stdout.read().decode("utf-8"))

    # Raise exception with stderr if the process failed
    if proc.returncode != 0:
        log.error(f"Error in running EtherSolve for {result_filename}, reason:\n {proc.stderr.read().decode('utf-8')}")
        raise Exception()

    # Log success
    log.info(f"Analysis for {result_filename} completed successfully")
