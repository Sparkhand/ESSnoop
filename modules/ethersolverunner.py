"""EtherSolve runner module

Runs EtherSolve.jar on a given .bytecode file and stores the outcome
in a .json file in the specified output directory.
"""


import os
from subprocess import PIPE, Popen

import modules.logger as logger

# region Module info

__all__ = ["run_ethersolve"]
__version__ = "1.0"
__author__ = "Davide Tarpini"


# endregion

# region Module functions


def run_ethersolve(contract_address: str,
                   jarfile: str,
                   input_dir: str,
                   output_dir: str,
                   log: logger.logging.Logger | None = None) -> str | None:
    """Runs EtherSolve.jar on a given .bytecode file and stores the
    outcome in a .json file in the specified output directory.

    Args:
        contract_address (str): the address of the smart contract.
        jarfile (str): the path to the EtherSolve.jar file.
        input_dir (str): the directory containing the .bytecode file.
        output_dir (str): the directory where the .json output file
                          will be saved.
        log (logger.logging.Logger | None, optional): the logger to use.

    Returns:
        str | None: if EtherSolve ran successfully, None is returned.
                    Otherwise, contract_address is returned.
    """

    # Compute input and output file paths
    INFILE_PATH: str = os.path.join(input_dir, f"{contract_address}.bytecode")

    if not os.path.exists(INFILE_PATH):
        if log is not None:
            log.error(f"Input file {INFILE_PATH} not found")
        return contract_address

    OUTFILE_PATH: str = os.path.join(output_dir, f"{contract_address}.json")

    if os.path.exists(OUTFILE_PATH):
        if log is not None:
            log.info(f"EtherSolve already executed for {contract_address}")
        return None

    # Log info to state EtherSolve being launched
    if log is not None:
        log.info(f"Running EtherSolve for {contract_address}")

    # Set command and its args
    command: list[str] = [
        "java",
        "-jar",
        jarfile,
        "-rj",
        INFILE_PATH,
        "-o",
        OUTFILE_PATH,
    ]

    # Run EtherSolve
    proc: Popen = Popen(command, stdout=PIPE, stderr=PIPE)
    proc.wait()

    # Log stdout if not empty
    stdout: str = proc.stdout.read().decode("utf-8")
    if stdout:
        if log is not None:
            log.info(stdout)

    # Signal error if stderr is not empty
    if proc.returncode != 0:
        if log is not None:
            log.error(f"Error in running EtherSolve for "
                      f"{contract_address}, reason:\n "
                      f"{proc.stderr.read().decode('utf-8')}"
                      )
        return contract_address

    # Log success
    if log is not None:
        log.info(f"EtherSolve successfully executed for {contract_address}")

    return None


# endregion
