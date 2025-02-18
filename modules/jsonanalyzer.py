"""JSON Analyzer module

This module is used to analyze the JSON output of EtherSolve and retrieve
a dictionary of stats about solved jumps. Stats such as the total number
of jumps are retrieved sintactically from the .opcodes file.
"""

import json
import os
from enum import Enum
from sre_constants import JUMP

import modules.logger as logger

# region Module info

__all__ = ["analyze"]
__version__ = "1.0"
__author__ = "Davide Tarpini"

# endregion

# region Module classes and enums


class NodeType(Enum):
    """Custom NodeType to classify opcodes.

    Extends the Enum class.
    """
    JUMP = 1
    JUMPI = 2
    JUMPDEST = 3
    OTHER = 4


class Analyzer:
    """The Analyzer class is responsible for analyzing a CFG stored
    in a JSON file and compute various stats about solved jumps.
    """

    def __init__(self, json_data: dict, address: str,
                 log: logger.logging.Logger | None = None):
        """The constructor of an Analyzer object.

        Args:
            json_data (dict): the JSON data containing the CFG.
            address (str): the address of the smart contract.
            log (logger.logging.Logger | None, optional): the logger to use.
                                                          Defaults to None.
        """

        self.__contract_address: str = address
        self.__cfg: dict = json_data["runtimeCfg"]
        self.__blocks: dict = self.__cfg["nodes"]
        self.__edges: dict = self.__cfg["successors"]
        self.__stats: dict = {
            "precisely_solved_jumps": 0,
            "soundly_solved_jumps": 0,
            "unreachable_jumps": 0,
            "unsolved_jumps": 0,
        }
        self.__log: logger.logging.Logger | None = log

    def __get_block(self, offset: int) -> dict:
        """Get the block with the given offset.

        Args:
            offset (int): integer offset of the block.

        Raises:
            Exception: if no such block is found.

        Returns:
            dict: the infos of the block as a dictionary.
        """

        for block in self.__blocks:
            if block["offset"] == offset:
                return block

        raise Exception(f"Block with offset {offset} not found at "
                        "__get_block")

    def __get_dests_from_offset(self, offset: int) -> list[int]:
        """Given a block offset, inspect the CFG edges and return its
        dests (outgoing edges). It makes sure dests are unique.

        Args:
            offset (int): integer offset of the block.

        Returns:
            list[int]: set of dests as integer offsets.
        """

        dests: list[int] = []

        for edge in self.__edges:
            if edge["from"] == offset:
                dests.extend(list(set(edge["to"])))

        return dests

    def __get_dests_from_block(self, block: dict) -> list[int]:
        """Given a block, inspect the CFG edges and return its dests
        (outgoing edges).

        Args:
            block (dict): a block represented as a dictionary.

        Returns:
            list[int]: set of dests as integer offsets.
        """

        block_offset = block["offset"]
        return self.__get_dests_from_offset(block_offset)

    def __get_op_type(self, op: str) -> NodeType:
        """Performs opcode classification using `NodeType` type.

        Args:
            op (str): a string representation of the opcode.

        Returns:
            NodeType: the corresponding `NodeType` inferred.
        """

        op = op.strip().upper()
        if op == "JUMP":
            return NodeType.JUMP
        if op == "JUMPI":
            return NodeType.JUMPI
        if op == "JUMPDEST":
            return NodeType.JUMPDEST
        return NodeType.OTHER

    def __get_first_last_opcodes(self,
                                 block: dict) -> tuple[NodeType, NodeType]:
        """Given a block as a dictionary, retrieves its first and last
        opcodes `NodeType`.

        Args:
            block (dict): the block, represented as a dictionary.

        Raises:
            Exception: if the block has no opcodes (malformed block).

        Returns:
            tuple[NodeType, NodeType]: the `NodeType` of the first and
                                       last opcode respectively.
        """

        parsedOps: str = block["parsedOpcodes"]
        parsedOps: str = parsedOps.split("\n")

        # Check for invalid block (no opcodes)
        if len(parsedOps) < 1:
            raise Exception("Block has less than 2 opcodes at "
                            "__get_first_last_opcodes")

        # Check for block with a single opcode
        if len(parsedOps) < 2:  # It means there is only one opcode
            cleaned: str = parsedOps[0].split(":")[1].strip()
            first: NodeType = self.__get_op_type(cleaned)

            return tuple((first, first))

        # Block with two or more opcodes
        cleaned: str = parsedOps[0].split(":")[1].strip()
        first: NodeType = self.__get_op_type(cleaned)

        cleaned = parsedOps[-1].split(":")[1].strip()
        last: NodeType = self.__get_op_type(cleaned)

        return tuple((first, last))

    def __is_precisely_solved(self, jump: NodeType, block: int) -> bool:
        """Given a jump, checks if it is precisely solved.
        A JUMP is precisely solved if:
        - it has exactly one destination; and
        - the destination is a JUMPDEST.

        A JUMPI is precisely solved if:
        - it has exactly two destinations; and
        - the first destination is a JUMPDEST; and
        - the second destination IS NOT a JUMPDEST.

        Args:
            jump (NodeType): the `NodeType` of the jump.
            block (int): the offset of the block.

        Raises:
            Exception: if block does not exists or is malformed.
            Exception: if the jump is not a JUMP nor a JUMPI.

        Returns:
            bool: True if the jump is precisely solved, False otherwise.
        """

        dests: list[int] = self.__get_dests_from_block(block)

        if jump == NodeType.JUMP:
            if len(dests) != 1:
                return False
            try:
                dest_block: dict = self.__get_block(dests[0])
                dest_op: NodeType
                dest_op, _ = self.__get_first_last_opcodes(dest_block)
                return dest_op == NodeType.JUMPDEST
            except Exception as e:
                raise Exception(str(e) + " at __is_precisely_solved")

        if jump == NodeType.JUMPI:
            if len(dests) != 2:
                return False

            try:
                block_fst_dst: dict = self.__get_block(dests[0])
                op_fst_dst: NodeType
                op_fst_dst, _ = self.__get_first_last_opcodes(block_fst_dst)

                block_snd_dst: dict = self.__get_block(dests[1])
                op_snd_dst: NodeType
                op_snd_dst, _ = self.__get_first_last_opcodes(block_snd_dst)

                if (op_fst_dst == NodeType.JUMPDEST
                    and op_snd_dst != NodeType.JUMPDEST
                    ) or (
                    op_fst_dst != NodeType.JUMPDEST
                    and op_snd_dst == NodeType.JUMPDEST
                ):
                    return True

                return False

            except Exception as e:
                raise Exception(str(e) + " at __is_precisely_solved")

        raise Exception("Trying to precisely solve a non-JUMP or "
                        "non-JUMPI opcode at __is_precisely_solved")

    def __is_soundly_solved(self, jump: NodeType, block: int) -> bool:
        """Given a jump, checks if it is soundly solved.
        A JUMP is soundly solved at least one of its destinations is a
        JUMPDEST.

        A JUMPI is soundly solved if at least one of its destinations is
        a JUMPDEST and another IS NOT a JUMPDEST.

        Args:
            jump (NodeType): the `NodeType` of the jump.
            block (int): the offset of the block.

        Raises:
            Exception: if block does not exists or is malformed.
            Exception: if the jump is not a JUMP nor a JUMPI.

        Returns:
            bool: True if the jump is soundly solved, False otherwise.
        """

        dests: list[int] = self.__get_dests_from_block(block)

        if jump == NodeType.JUMP:
            if len(dests) < 1:
                return False
            try:
                for dest in dests:
                    dest_block: dict = self.__get_block(dest)
                    dest_op: NodeType
                    dest_op, _ = self.__get_first_last_opcodes(dest_block)

                    if dest_op == NodeType.JUMPDEST:
                        return True
                return False

            except Exception as e:
                raise Exception(str(e) + " at __is_soundly_solved")

        if jump == NodeType.JUMPI:
            if len(dests) < 2:
                return False

            jumpdest_found: bool = False
            non_jumpdest_found: bool = False

            try:
                for dest in dests:
                    dest_block: dict = self.__get_block(dest)
                    dest_op: NodeType
                    dest_op, _ = self.__get_first_last_opcodes(dest_block)

                    if dest_op == NodeType.JUMPDEST:
                        jumpdest_found = True
                    else:
                        non_jumpdest_found = True

                    if jumpdest_found and non_jumpdest_found:
                        return True
                return False

            except Exception as e:
                raise Exception(str(e) + " at __is_soundly_solved")

        raise Exception("Trying to soundly solve a non-JUMP or "
                        "non-JUMPI opcode at __is_soundly_solved")

    def __is_unreachable_block(self, target_offset: int, entrypoint: int = 0) -> bool:
        """Checks if a block is unreachable from the entrypoint
        performing a depth-first search. 

        Args:
            target_offset (int): the offset of the block to be checked.
            entrypoint (int, optional): the offset of the entrypoint.
                                        Defaults to 0.

        Returns:
            bool: True if the block is unreachable, False otherwise.
        """

        visited: set[int] = set()  # Set to keep track of visited blocks
        stack: list[int] = [entrypoint]  # Stack to perform DFS

        # If there is something in the stack, it means there are paths to explore
        while stack:
            current_offset: int = stack.pop()
            visited.add(current_offset)

            if current_offset == target_offset:
                return False  # Block is reachable

            # Get the destinations of the current block
            dests: list[int] = self.__get_dests_from_offset(current_offset)

            # Append the destinations to the stack if they haven't been visited
            for dest in dests:
                if dest not in visited:
                    stack.append(dest)

        return True  # Block is unreachable

    def analyze_jumps(self) -> tuple[dict, bool]:
        """Analyzes the jumps in the CFG.

        Raises:
            Exception: if block does not exists or is malformed.

        Returns:
            tuple[dict, bool]: a dictionary with stats about analyzed
                               jumps and a boolean indicating if there
                               were any errors during the analysis.
        """

        encountered_errors: bool = False

        # For every block in the CFG we check if it has a JUMP or JUMPI
        # as its last opcode. If so, it is worth analyzing.
        for block in self.__blocks:
            try:
                last: NodeType
                _, last = self.__get_first_last_opcodes(block)

                if last != NodeType.JUMP and last != NodeType.JUMPI:
                    continue
            except Exception as e:  # Malformed block
                encountered_errors = True
                self.__log.error(f"ADDRESS: {self.__contract_address}"
                                 f" - BLOCK: {block['offset']} - {e}")
                continue

            # At this point, it is necessary to check if the jump was
            # solved and how it was solved. If it's not solved, it might
            # be unreachable. If it's reachable, then it's marked
            # as unsolved.
            if self.__log is not None:
                self.__log.info(f"ADDRESS: {self.__contract_address} - "
                                f"BLOCK: {block['offset']} - "
                                f"Examining {last}")

            try:
                if self.__is_precisely_solved(last, block):
                    self.__stats["precisely_solved_jumps"] += 1

                    if self.__log is not None:
                        self.__log.info(f"ADDRESS: {self.__contract_address} "
                                        f"-BLOCK: {block['offset']} "
                                        f"- {last} is precisely solved")

                elif self.__is_soundly_solved(last, block):
                    self.__stats["soundly_solved_jumps"] += 1

                    if self.__log is not None:
                        self.__log.info(f"ADDRESS: {self.__contract_address} "
                                        f"-BLOCK: {block['offset']} "
                                        f"- {last} is soundly solved")

                elif self.__is_unreachable_block(block["offset"]):
                    self.__stats["unreachable_jumps"] += 1

                    if self.__log is not None:
                        self.__log.info(f"ADDRESS: {self.__contract_address} "
                                        f"-BLOCK: {block['offset']} "
                                        f"- {last} is unreachable")

                else:
                    self.__stats["unsolved_jumps"] += 1

                    if self.__log is not None:
                        self.__log.info(f"ADDRESS: {self.__contract_address} "
                                        f"-BLOCK: {block['offset']} "
                                        f"- {last} is unsolved")

            except Exception as e:
                self.__stats["unsolved_jumps"] += 1
                encountered_errors = True
                if self.__log is not None:
                    self.__log.error(f"ADDRESS: {self.__contract_address}"
                                     f" - BLOCK: {block['offset']} - {e}")
                continue

        return (self.__stats, encountered_errors)


# endregion

# region Module functions

def get_total_opcodes(filename: str) -> int:
    """Given the filename of a .opcodes files, counts the total number
    of opcodes.

    Args:
        filename (str): the filename of the .opcodes file.

    Returns:
        int: the total number of opcodes.
    """
    count: int = 0

    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line:
                count += 1

    return count


def get_total_jumps(filename: str) -> int:
    """Given the filename of a .opcodes files, counts the total number
    of jumps (JUMP or JUMPI opcodes).

    Args:
        filename (str): the filename of the .opcodes file.

    Returns:
        int: the total number of jumps.
    """

    count: int = 0

    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line == "JUMP" or line == "JUMPI":
                count += 1

    return count

def get_total_orphan_jumps(filename: str) -> int:
    """Given the filename of a .opcodes files, counts the total number
    of orphan jumps (JUMP which are not preceded by a PUSH).

    Args:
        filename (str): the filename of the .opcodes file.

    Returns:
        int: the total number of orphan jumps.
    """

    count: int = 0
    last_push: bool = False

    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line.startswith("PUSH"):
                last_push = True
            elif line == "JUMP":
                if not last_push:
                    count += 1
                last_push = False
            else:
                last_push = False

    return count


def analyze(contract_address: str, opcodes_dir: str, json_dir: str,
            log: logger.logging.Logger | None = None) -> tuple[dict, str | None]:
    """Analyze the JSON files produced by EtherSolve analysis on the
    specified smart contract address.

    Args:
        contract_address (str): the address of the smart contract.
        opcodes_dir (str): the directory with the .opcodes files.
        json_dir (str): the directory with the .json files.
        log (logger.logging.Logger | None, optional): logger to use.
                                                      Defaults to None.

    Returns:
        tuple[dict, str | None]: a tuple with a dictionary containing
                                 the computed stats, and a string
                                 corresponding to the smart contract
                                 address if the analysis encountered
                                 errors (None otherwise).
    """

    # Compute the input path for opcodes and JSON
    INFILE_OP: str = os.path.join(opcodes_dir, f"{contract_address}.opcodes")
    INFILE_JSON: str = os.path.join(json_dir, f"{contract_address}.json")

    if not os.path.exists(INFILE_OP):
        log.error(f"Opcodes file {INFILE_OP} not found")
        return {}, contract_address

    if not os.path.exists(INFILE_JSON):
        log.error(f"JSON file {INFILE_JSON} not found")
        return {}, contract_address

    # Stats dictionary
    STATS: dict = {
        "Smart Contract": contract_address,
        "Total Opcodes": 0,
        "Total Jumps": 0,
        "Solved Jumps": 0,
        "Orphan Jumps": 0,
        "Precisely Solved Jumps": 0,
        "Soundly Solved Jumps": 0,
        "Pending Jumps": 0,
        "Unreachable Jumps": 0,
        "Unsolved Jumps": 0,
    }

    # Retrieve total number of opcodes and total number of jumps
    STATS["Total Opcodes"] = get_total_opcodes(INFILE_OP)
    STATS["Total Jumps"] = get_total_jumps(INFILE_OP)
    STATS["Orphan Jumps"] = get_total_orphan_jumps(INFILE_OP)

    # Retrieve JSON data
    with open(INFILE_JSON, "r") as file:
        JSON_DATA = json.load(file)

    # For the other stats, analyze the JSON file with the Analyzer
    analyzer: Analyzer = Analyzer(JSON_DATA, contract_address, log)
    JUMP_STATS, ENCOUNTERED_ERRORS = analyzer.analyze_jumps()
    del analyzer
    
    
    # Compute additional stats
    STATS["Solved Jumps"] = (JUMP_STATS["precisely_solved_jumps"]
                             + JUMP_STATS["soundly_solved_jumps"])

    STATS["Precisely Solved Jumps"] = JUMP_STATS["precisely_solved_jumps"]
    STATS["Soundly Solved Jumps"] = JUMP_STATS["soundly_solved_jumps"]

    # Seek for missing jumps
    MISSING_JUMPS: int = (STATS["Total Jumps"]
                          - (STATS["Solved Jumps"]
                             + STATS["Pending Jumps"]))

    if MISSING_JUMPS > 0:
        ENCOUNTERED_ERRORS = True
        if log is not None:
            log.error(f"ADDRESS: {contract_address} - "
                        f"Number of missing jumps: {MISSING_JUMPS}")

    # Missing jumps are considered unreachable jumps
    JUMP_STATS["unreachable_jumps"] += MISSING_JUMPS

    # Recalculate pending jumps
    STATS["Pending Jumps"] = (JUMP_STATS["unsolved_jumps"]
                                 + JUMP_STATS["unreachable_jumps"])

    STATS["Unreachable Jumps"] = JUMP_STATS["unreachable_jumps"]
    STATS["Unsolved Jumps"] = JUMP_STATS["unsolved_jumps"]

    # Return stats and contract address
    # (the latter only if encountered errors is True)

    if log is not None:
        log.info(f"ADDRESS: {contract_address} - "
                 f"Finished analyzing JSON")
    return (STATS, contract_address if ENCOUNTERED_ERRORS else None)

# endregion
