"""Etherscan downloader module

Downloads runtime bytecode from Etherscan API using API key.
Makes a request to Etherscan API to get the runtime bytecode of a
contract using the contract's address. The API key is required to make
the request.
"""


import os

import requests

import modules.logger as logger

# region Module info

__all__ = ["download_bytecode"]
__version__ = "1.0"
__author__ = "Davide Tarpini"


# endregion


# region Module functions

def download_bytecode(contract_address: str,
                      output_dir: str,
                      api_key: str,
                      log: logger.logging.Logger | None = None) -> str | None:
    """Downloads the runtime bytecode of a single smart contract from
    Etherscan API.

    Args:
        contract_address (str): the address of the smart contract.
        output_dir (str): the output directory where the bytecode
                          will be saved.
        api_key (str): the Etherscan API key.
        log (logger.logging.Logger | None, optional): the logger to use.

    Returns:
        str | None: if the bytecode was downloaded successfully, None is
                    returned. Otherwise, contract_address is returned.
    """

    # Compute the output file path
    OUTFILE_PATH: str = os.path.join(output_dir,
                                     f"{contract_address}.bytecode")

    # Check if the contract was already downloaded
    if os.path.exists(OUTFILE_PATH):
        if log is not None:
            log.info(f"Contract {contract_address} already downloaded")
        return None

    if log is not None:
        log.info(f"Downloading bytecode for contract {contract_address}")

    # Make a request to Etherscan API to get the runtime bytecode
    # of the contract
    MODULE: str = "proxy"
    ACTION: str = "eth_getCode"
    URL: str = (f"https://api.etherscan.io/api?module={MODULE}&action={ACTION}"
                f"&address={contract_address}&apikey={api_key}")

    JSON_RESPONSE: dict
    try:
        JSON_RESPONSE = requests.get(URL).json()
    except ConnectionError:
        if log is not None:
            log.error(f"Bytecode download failed for contract "
                      f"{contract_address} due to connection error")
        return contract_address
    except Exception as e:
        if log is not None:
            log.error(f"Bytecode download failed for contract "
                      f"{contract_address} with the following error: "
                      f"{e}")
        return contract_address

    # If the API call encounters an error, the response will have
    # a "status" key with a value of "0" and a "result" key with
    # the error message

    if "status" in JSON_RESPONSE and JSON_RESPONSE["status"] == "0":
        if log is not None:
            log.error(f"Bytecode download failed for contract "
                      f"{contract_address} with the following error: "
                      f"{JSON_RESPONSE['result']}")
        return contract_address

    # If no error was encountered, the response will have a "result"
    # key with the bytecode

    if "result" not in JSON_RESPONSE:
        if log is not None:
            log.error(f"Bytecode download failed for contract "
                      f"{contract_address} with the following error: "
                      f"response is missing 'result' key")
        return contract_address

    result: str = JSON_RESPONSE["result"]

    # Save the bytecode to a file
    with open(OUTFILE_PATH, "w") as file:
        file.write(result)

    if log is not None:
        log.info(f"Contract {contract_address} downloaded successfully")

    return None


# endregion
