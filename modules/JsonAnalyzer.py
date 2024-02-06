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
    # |- contract_address: The address of the contract
    # |- cfg: The runtimeCfg object
    # |- blocks: The nodes (blocks) of the CFG
    # |- edges: The edges of the CFG
    # |- metrics: A dictionary to store the metrics
    def __init__(self, filename: str):
        with open(filename, "r") as file:
            data = json.load(file)
        self.__contract_address = filename.split("/")[-1].split(".")[0]
        self.__cfg = data["runtimeCfg"]
        self.__blocks = self.__cfg["nodes"]
        self.__edges = self.__cfg["successors"]
        self.__metrics = {
            "precisely_solved_jumps": 0,
            "soundly_solved_jumps": 0,
            "unreachable_jumps": 0,
        }

    # Given a block offset, it returns the block
    def __get_block(self, offset: int or str) -> dict:
        offset = int(offset)

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
        op = op.strip()
        if op == "JUMP":
            return NodeType.JUMP
        if op == "JUMPI":
            return NodeType.JUMPI
        if op == "JUMPDEST":
            return NodeType.JUMPDEST
        return NodeType.OTHER

    # Returns a tuple with the first and last opcodes of a block
    # (first, last)
    def __get_block_first_last_opcodes(self, block: dict) -> tuple:
        parsedOps = block["parsedOpcodes"]
        parsedOps = parsedOps.split("\n")
        if len(parsedOps) < 1:  # Invalid block (no opcodes)
            raise Exception(
                "Block with offset {block['offset']} has less than 2 opcodes"
            )

        if len(parsedOps) < 2:  # It means there is only one opcode
            cleaned = parsedOps[0].split(":")[1].strip()
            first = self.__get_op_type(cleaned)
            return tuple((first, first))

        cleaned = parsedOps[0].split(":")[1].strip()
        first = self.__get_op_type(cleaned)
        cleaned = parsedOps[-1].split(":")[1].strip()
        last = self.__get_op_type(cleaned)
        return tuple((first, last))

    # Given a jump and its block, it returns True if the jump is precisely
    # solved, False otherwise.
    # A JUMP is precisely solved if it has a JUMPDEST as its one and only
    # destination.
    # A JUMPI is precisely solved if it has exactly two destinations:
    # |- a JUMPDEST
    # |- a non-JUMPDEST
    def __is_precisely_solved(self, jump: NodeType, block: dict) -> bool:
        dests = self.__get_dests(block)

        if jump == NodeType.JUMP:
            if len(dests) != 1:
                return False
            try:
                dest_block = self.__get_block(dests[0])
                dest_op = self.__get_block_first_last_opcodes(dest_block)[0]
                return dest_op == NodeType.JUMPDEST
            except Exception as e:
                raise Exception(str(e))

        if jump == NodeType.JUMPI:
            if len(dests) != 2:
                return False

            try:
                first_dest_block = self.__get_block(dests[0])
                first_dest_op, _ = self.__get_block_first_last_opcodes(first_dest_block)

                second_dest_block = self.__get_block(dests[1])
                second_dest_op, _ = self.__get_block_first_last_opcodes(
                    second_dest_block
                )

                if (
                    first_dest_op == NodeType.JUMPDEST
                    and second_dest_op != NodeType.JUMPDEST
                ) or (
                    first_dest_op != NodeType.JUMPDEST
                    and second_dest_op == NodeType.JUMPDEST
                ):
                    return True
                return False
            except Exception as e:
                raise Exception(str(e))

        raise Exception("Trying to precisely solve a non-JUMP or non-JUMPI opcode")

    # Given a jump and its block, it returns True if the jump is soundly
    # solved, False otherwise.
    # A JUMP is soundly solved if it has a JUMPDEST as one of its destinations
    # and the other destination is unreachable.
    # A JUMPI is soundly solved if it has a JUMPDEST as one of its destinations
    # and one of the other destinations is a non-JUMPDEST
    def __is_soundly_solved(self, jump: NodeType, block: dict) -> bool:
        dests = self.__get_dests(block)

        if jump == NodeType.JUMP:
            if len(dests) < 1:
                return False
            try:
                for dest in dests:
                    dest_block = self.__get_block(dest)
                    dest_op = self.__get_block_first_last_opcodes(dest_block)[0]
                    if dest_op == NodeType.JUMPDEST:
                        return True
                return False
            except Exception as e:
                raise Exception(str(e))

        if jump == NodeType.JUMPI:
            if len(dests) < 2:
                return False

            jumpdest_found = False
            non_jumpdest_found = False
            try:
                for dest in dests:
                    dest_block = self.__get_block(dest)
                    dest_op = self.__get_block_first_last_opcodes(dest_block)[0]
                    if dest_op == NodeType.JUMPDEST:
                        jumpdest_found = True
                    else:
                        non_jumpdest_found = True

                    if jumpdest_found and non_jumpdest_found:
                        return True
                return False
            except Exception as e:
                raise Exception(str(e))

        raise Exception("Trying to soundly solve a non-JUMP or non-JUMPI opcode")

    # Given a jump and its block, it returns True if the jump is unreachable,
    # False otherwise.
    # A JUMP or a JUMPI is unreachable if, starting from the entry point of the
    # CFG (block with offset 0) there is no path to the block containing the jump.
    def __is_unreachable(
        self, jump: NodeType, block: dict, entrypoint: str = "0"
    ) -> bool:
        return False

    # Analyze the graph and produce a report
    def analyze(self) -> dict:
        # For every block in the CFG we check if it has a JUMP or JUMPI as
        # its last opcode.
        for block in self.__blocks:
            try:
                _, last = self.__get_block_first_last_opcodes(block)
                if last != NodeType.JUMP and last != NodeType.JUMPI:
                    continue
            except Exception as e:
                log.error(
                    f"ADDRESS: {self.__contract_address} - BLOCK: {block['offset']} - {e}"
                )
                raise Exception()

            log.info(
                f"ADDRESS: {self.__contract_address} - BLOCK: {block['offset']} - Examining {last}"
            )

            # At this point, it is necessary to check if the jump was solved
            # and how it was solved. If it's not solved, it might be unreachable.
            # If it's reachable, then it's marked as unsolved.

            try:
                if self.__is_precisely_solved(last, block):
                    log.info(
                        f"ADDRESS: {self.__contract_address} - BLOCK: {block['offset']} - {last} is precisely solved"
                    )
                    self.__metrics["precisely_solved_jumps"] += 1
                elif self.__is_soundly_solved(last, block):
                    log.info(
                        f"ADDRESS: {self.__contract_address} - BLOCK: {block['offset']} - {last} is soundly solved"
                    )
                    self.__metrics["soundly_solved_jumps"] += 1
                elif self.__is_unreachable(last, block):
                    log.info(
                        f"ADDRESS: {self.__contract_address} - BLOCK: {block['offset']} - {last} is unreachable"
                    )
                    self.__metrics["unreachable_jumps"] += 1
                else:
                    log.info(
                        f"ADDRESS: {self.__contract_address} - BLOCK: {block['offset']} - {last} is unsolved"
                    )
            except Exception as e:
                log.error(
                    f"ADDRESS: {self.__contract_address} - BLOCK: {block['offset']} - {e}"
                )
                raise Exception()

        log.info(f"ADDRESS: {self.__contract_address} - Finished analyzing JSON")
        return self.__metrics
