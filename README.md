# ESSnoop - EtherSolve Snoop 🔎

EtherSolve Snoop is a Python with various submodules which aims at running [EtherSolve](https://github.com/SeUniVr/EtherSolve) for a batch of smart contracts addresses and analyze the outcomes of EtherSolve analysis on the contracts to compute stats of interest.

Currently, the tool checks the CFG built by EtherSolve and infers how many JUMP and JUMPI instructions were solved. It then compares them to the actual number of jumps in the contract and computes additional stats between the two. It infers also _how_ every single jump was solved.

## Usage 📖

First, make sure you have all the dependencies installed.

```
pip install -r requirements.txt
```

You can run the tool with the following command:

```
python3 essnoop.py <input-file>
```

Wanna know the available options?

```
python3 essnoop.py --help
```

```
ESSnoop - EtherSolve Snoop | Analyzes smart contracts using EtherSolve and computes stats on analysis
outcomes.

positional arguments:
  input-filename        File containing the list of smart contracts to analyze.

options:
  -h, --help            show this help message and exit
  -o CSV_OUTFILE, --csv-outfile CSV_OUTFILE
                        CSV output filename.
  -b, --preserve-bytecode
                        Preserve downloaded bytecode so it doesn't have to be downloaded again.
  -p, --preserve-all    Preserve all output directories and files (bytecode, opcodes, json). It overrides
                        -b flag.
  -k ETHERSCAN_API_KEY, --etherscan-api-key ETHERSCAN_API_KEY
                        Specifiy your Etherscan API key. This is useful if you haven't set
                        ETHERSCAN_API_KEY environment variable.
  -j ETHERSOLVE_JAR, --ethersolve-jar ETHERSOLVE_JAR
                        Specify the name of the EtherSolve jar file (include .jar).

```

## API Key for Etherscan

Hey, this is important! This tool uses [Etherscan API](https://etherscan.io/apis) to retrieve contract bytecode from the Ethereum blockchain. If you don't have an API key, you can [follow a guide togenerate one here](https://info.etherscan.com/api-keys/).

The API key must be set as an environment variable called `ETHERSCAN_API_KEY` or it can be specified via the `-k --etherscan-api-key` CLI option.
