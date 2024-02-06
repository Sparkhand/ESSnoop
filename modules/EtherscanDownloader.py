###########################################################
# Python module to download runtime bytecode from Etherscan API using API key.
# Make a request to Etherscan API to get the runtime bytecode of a contract
# using the contract's address. The API key is required to make the request.
###########################################################

import requests
import time
import os
import modules.Logger as Logger

# Logger
log = Logger.get_logger(__name__)


# Downlod a single contract bytecode
def download_bytecode(output_dir: str, contract_address: str, api_key: str):
    # Check if the output dir exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Check if the contract was already downloaded
    if os.path.exists(os.path.join(output_dir, f"{contract_address}.bytecode")):
        log.info(f"Bytecode for contract {contract_address} already exists")
        return

    # Make a request to Etherscan API to get the runtime bytecode of the contract
    module = "proxy"
    action = "eth_getCode"
    url = f"https://api.etherscan.io/api?module={module}&action={action}&address={contract_address}&apikey={api_key}"

    log.info(f"Downloading bytecode for contract {contract_address}")
    response = requests.get(url)
    result = response.json()["result"]

    # Error handling
    if "error" in result.lower():
        raise Exception(
            f"[{result}] error in downloading bytecode for contract {contract_address}"
        )

    # Save the bytecode to a file
    filename = f"{contract_address}.bytecode"
    with open(os.path.join(output_dir, filename), "w") as file:
        file.write(result)
        log.info(f"Successfully downloaded bytecode for contract {contract_address}")


# Download bytecode for a list of contracts (addresses in a file)
def batch_download_bytecode(input_file: str, output_dir: str, api_key: str):
    # Check if the output dir exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # For each line in the input file, download the bytecode of the contract
    with open(input_file, "r") as file:
        count = 0
        for line in file:
            contract_address = line.strip()

            try:
                download_bytecode(output_dir, contract_address, api_key)
            except Exception as e:
                log.error(str(e))

            # Pause every 5 requests to avoid rate limiting
            count += 1
            if count % 5 == 0:
                time.sleep(0.005)
