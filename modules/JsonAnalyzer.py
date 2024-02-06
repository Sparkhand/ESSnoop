###########################################################
# Python module to analyze the JSON output of EtherSolve and retrieve various
# stats about solved jumps
###########################################################

import modules.Logger as Logger
import json
from enum import Enum

# Logger
log = Logger.get_logger(__name__)

# An enum to classify a single opcode
class NodeType(Enum):
    JUMP = 1
    JUMPI = 2
    JUMPDEST = 3
    OTHER = 4


class Analyzer:
    # Constructor. Class has instance variables:
    # |- cfg: The runtimeCfg object
    # |- blocks: The nodes (blocks) of the CFG
    # |- edges: The edges of the CFG
    # |- metrics: A dictionary to store the metrics
    def __init__(self, filename: str):
        with open(filename, "r") as file:
            data = json.load(file)
        self.__cfg = data["runtimeCfg"]
        self.__blocks = self.__cfg["nodes"]
        self.__edges = self.__cfg["successors"]
        self.__metrics = {
            "precisely_solved_jumps": 0,
            "soundly_solved_jumps": 0,
            "unreachable_jumps": 0,
        }

    # Given a block offset, it returns the block
    def __get_block(self, offset: str or int) -> dict:
        offset = str(offset)
        for block in self.__blocks:
            if block["offset"] == offset:
                return block
        raise Exception(f"Block with offset {offset} not found")

    # Given a block, it returns its destinations
    def __get_dests(self, block: dict) -> list:
        block_offset = block["offset"]
        for edge in self.__edges:
            if edge["from"] == block_offset:
                return edge["to"]
        return []

    # Given a string representing an opcode, it returns its type
    def __get_op_type(self, op: str) -> NodeType:
        if "JUMP" in op:
            return NodeType.JUMP
        if "JUMPI" in op:
            return NodeType.JUMPI
        if "JUMPDEST" in op:
            return NodeType.JUMPDEST
        return NodeType.OTHER

    # Returns a tuple with the first and last opcodes of a block
    # (first, last)
    def __get_block_first_last_opcodes(self, block: dict) -> tuple:
        parsedOps = block["parsedOpcodes"]
        parsedOps = parsedOps.split("\n")
        if len(parsedOps) < 2:  # Invalid block (no opcodes)
            raise Exception(
                f"Block with offset {block['offset']} has less than 2 opcodes"
            )
            
        if len(parsedOps) < 3:  # It means there is only one opcode
            first = self.__get_op_type(parsedOps[0])
            return tuple((first, first))
        
        return tuple(
            (self.__get_op_type(parsedOps[0]), self.__get_op_type(parsedOps[-2]))
        )

    # Analyze the graph and produce a report
    def analyze(self) -> dict:
        log.info("It works! For now...")
        print("It works! For now...")
