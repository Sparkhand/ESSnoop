###########################################################
# Python module to parse a file containing the bytecode of a contract and
# extract its opcodes in a .opcodes file.
###########################################################

import modules.Logger as Logger
import os

# Logger
log = Logger.get_logger(__name__)


def parseBytecode(input_file: str, output_dir: str):
    result_filename = os.path.basename(input_file).split(".")[0]

    # Read bytecode from input file
    with open(input_file, "r") as file:
        bytecode = file.read()

    # Check if bytecode has at least one opcode
    if len(bytecode) < 4:
        raise Exception(f"Bytecode for contract {result_filename} is too short")

    # Check if bytecode starts with 0x
    if bytecode[:2] != "0x":
        raise Exception(
            f"Bytecode for contract {result_filename} does not start with 0x"
        )

    bytecode = bytecode[2:]

    outfile = os.path.join(output_dir, f"{result_filename}.opcodes")

    with open(outfile, "w") as file:
        i = 0
        while i < len(bytecode):
            opcode = bytecode[i : i + 2]
            bytesForVal = pushBytes(opcode)
            if bytesForVal == 0:  # Opcode is not a PUSH (or maybe is a PUSH0)
                file.write(f"{getOpcodeString(opcode)}\n")
            else:  # Opcode is a PUSH
                file.write(f"PUSH{bytesForVal} 0x{bytecode[i+2:i+2+bytesForVal*2]}\n")
                i += bytesForVal * 2
            i += 2

def getOpcodeString(opcode: str) -> str:
    match opcode:
        case "00":
            return "STOP"
        case "01":
            return "ADD"
        case "02":
            return "MUL"
        case "03":
            return "SUB"
        case "04":
            return "DIV"
        case "05":
            return "SDIV"
        case "06":
            return "MOD"
        case "07":
            return "SMOD"
        case "08":
            return "ADDMOD"
        case "09":
            return "MULMOD"
        case "0a":
            return "EXP"
        case "0b":
            return "SIGNEXTEND"
        case "10":
            return "LT"
        case "11":
            return "GT"
        case "12":
            return "SLT"
        case "13":
            return "SGT"
        case "14":
            return "EQ"
        case "15":
            return "ISZERO"
        case "16":
            return "AND"
        case "17":
            return "OR"
        case "18":
            return "XOR"
        case "19":
            return "NOT"
        case "1a":
            return "BYTE"
        case "1b":
            return "SHL"
        case "1c":
            return "SHR"
        case "1d":
            return "SAR"
        case "20":
            return "SHA3"
        case "30":
            return "ADDRESS"
        case "31":
            return "BALANCE"
        case "32":
            return "ORIGIN"
        case "33":
            return "CALLER"
        case "34":
            return "CALLVALUE"
        case "35":
            return "CALLDATALOAD"
        case "36":
            return "CALLDATASIZE"
        case "37":
            return "CALLDATACOPY"
        case "38":
            return "CODESIZE"
        case "39":
            return "CODECOPY"
        case "3a":
            return "GASPRICE"
        case "3b":
            return "EXTCODESIZE"
        case "3c":
            return "EXTCODECOPY"
        case "3d":
            return "RETURNDATASIZE"
        case "3e":
            return "RETURNDATACOPY"
        case "3f":
            return "EXTCODEHASH"
        case "40":
            return "BLOCKHASH"
        case "41":
            return "COINBASE"
        case "42":
            return "TIMESTAMP"
        case "43":
            return "NUMBER"
        case "44":
            return "DIFFICULTY"
        case "45":
            return "GASLIMIT"
        case "46":
            return "CHAINID"
        case "47":
            return "SELFBALANCE"
        case "48":
            return "BASEFEE"
        case "49", "4f":
            return "INVALID"
        case "50":
            return "POP"
        case "51":
            return "MLOAD"
        case "52":
            return "MSTORE"
        case "53":
            return "MSTORE8"
        case "54":
            return "SLOAD"
        case "55":
            return "SSTORE"
        case "56":
            return "JUMP"
        case "57":
            return "JUMPI"
        case "58":
            return "PC"
        case "59":
            return "MSIZE"
        case "5a":
            return "GAS"
        case "5b":
            return "JUMPDEST"
        case "5f":
            return "PUSH0"
        case "80":
            return "DUP1"
        case "81":
            return "DUP2"
        case "82":
            return "DUP3"
        case "83":
            return "DUP4"
        case "84":
            return "DUP5"
        case "85":
            return "DUP6"
        case "86":
            return "DUP7"
        case "87":
            return "DUP8"
        case "88":
            return "DUP9"
        case "89":
            return "DUP10"
        case "8a":
            return "DUP11"
        case "8b":
            return "DUP12"
        case "8c":
            return "DUP13"
        case "8d":
            return "DUP14"
        case "8e":
            return "DUP15"
        case "8f":
            return "DUP16"
        case "90":
            return "SWAP1"
        case "91":
            return "SWAP2"
        case "92":
            return "SWAP3"
        case "93":
            return "SWAP4"
        case "94":
            return "SWAP5"
        case "95":
            return "SWAP6"
        case "96":
            return "SWAP7"
        case "97":
            return "SWAP8"
        case "98":
            return "SWAP9"
        case "99":
            return "SWAP10"
        case "9a":
            return "SWAP11"
        case "9b":
            return "SWAP12"
        case "9c":
            return "SWAP13"
        case "9d":
            return "SWAP14"
        case "9e":
            return "SWAP15"
        case "9f":
            return "SWAP16"
        case "a0":
            return "LOG0"
        case "a1":
            return "LOG1"
        case "a2":
            return "LOG2"
        case "a3":
            return "LOG3"
        case "a4":
            return "LOG4"
        case "f0":
            return "CREATE"
        case "f1":
            return "CALL"
        case "f2":
            return "CALLCODE"
        case "f3":
            return "RETURN"
        case "f4":
            return "DELEGATECALL"
        case "f5":
            return "CREATE2"
        case "fa":
            return "STATICCALL"
        case "fd":
            return "REVERT"
        case "fe":
            return "INVALID"
        case "ff":
            return "SELFDESTRUCT"
        case _:
            return f"'{opcode}'(Unknown Opcode)"


def pushBytes(opcode: str) -> int:
    match opcode:
        case "60":
            return 1
        case "61":
            return 2
        case "62":
            return 3
        case "63":
            return 4
        case "64":
            return 5
        case "65":
            return 6
        case "66":
            return 7
        case "67":
            return 8
        case "68":
            return 9
        case "69":
            return 10
        case "6a":
            return 11
        case "6b":
            return 12
        case "6c":
            return 13
        case "6d":
            return 14
        case "6e":
            return 15
        case "6f":
            return 16
        case "70":
            return 17
        case "71":
            return 18
        case "72":
            return 19
        case "73":
            return 20
        case "74":
            return 21
        case "75":
            return 22
        case "76":
            return 23
        case "77":
            return 24
        case "78":
            return 25
        case "79":
            return 26
        case "7a":
            return 27
        case "7b":
            return 28
        case "7c":
            return 29
        case "7d":
            return 30
        case "7e":
            return 31
        case "7f":
            return 32
        case _:
            return 0
