###########################################################
# Python module to analzye dot files and retrieve count of solved jumps,
# total jumps and jumpdests through pydot
###########################################################

import pydot
from enum import Enum


# Enum to classify a single opcode
class NodeType(Enum):
    JUMP = 1
    JUMPI = 2
    JUMPDEST = 3
    OTHER = 4


###########################################################
# UNREACHABLE JUMP or JUMPI
###########################################################


# Unreachable JUMP or JUMPI => The block contains a JUMP or JUMPI but there
# are no edges entering the block.
def is_unreachable(edges: list, start_block_id: str) -> bool:
    # If the block is the first block, it is reachable
    if start_block_id == "0":
        return False

    # If there are no edges entering the block, it is unreachable
    for edge in edges:
        if edge.get_destination() == start_block_id:
            return False
    return True


###########################################################
# SOLVED JUMP
###########################################################


# Precisely solved JUMP => Only one JUMPDEST and exactly one destination.
def is_precisely_solved_jump(dests: list, blocks: dict) -> bool:
    if len(dests) != 1:
        return False

    dest = dests[0]

    return blocks[dest]["start"]["type"] == NodeType.JUMPDEST


# Soundly solved JUMP => At least one JUMPDEST among the destinations.
def is_soundly_solved_jump(dests: list, blocks: dict) -> bool:
    if len(dests) <= 0:
        return False

    for dest in dests:
        if blocks[dest]["start"]["type"] == NodeType.JUMPDEST:
            return True
    return False


###########################################################
# SOLVED JUMPI
###########################################################


# Precisely solved JUMPI => Only one JUMPDEST and one non-JUMPDEST destination.
def is_precisely_solved_jumpi(dests: list, blocks: dict) -> bool:
    if len(dests) != 2:
        return False

    if (
        blocks[dests[0]]["start"]["type"] == NodeType.JUMPDEST
        and blocks[dests[1]]["start"]["type"] == NodeType.OTHER
    ):
        return True

    if (
        blocks[dests[1]]["start"]["type"] == NodeType.JUMPDEST
        and blocks[dests[0]]["start"]["type"] == NodeType.OTHER
    ):
        return True

    return False


# Soundly solved JUMPI => At least two destinations, at least one JUMPDEST
def is_soundly_solved_jumpi(dests: list, blocks: dict) -> bool:
    if len(dests) < 2:
        return False

    for dest in dests:
        if blocks[dest]["start"]["type"] == NodeType.JUMPDEST:
            return True

    return False


###########################################################
# DOT ANALYSIS HELPER FUNCTIONS
###########################################################


# Retrieve solved destination for a jump or jumpi
def get_dests(edges, start_block_id):
    dests = []
    for edge in edges:
        if edge.get_source() == start_block_id:
            dests.append(edge.get_destination())
    return dests


# Retrieve a list of all the blocks
def classify_blocks_in_out(graph: pydot.Graph) -> dict:
    result = {}
    blocks = graph.get_nodes()

    for block in blocks:
        if "label" in block.get_attributes():
            label = block.get_attributes()["label"]
            if label is not None:
                label = label.replace('"', "")
                nodes = label.split("\\l")
                start_node = nodes[0]
                start_node_id = start_node.split(":")[0].strip()
                start_node_opcode = start_node.split(":")[1].strip()
                start_node_type = NodeType.OTHER

                match start_node_opcode:
                    case "JUMP":
                        start_node_type = NodeType.JUMP
                    case "JUMPI":
                        start_node_type = NodeType.JUMPI
                    case "JUMPDEST":
                        start_node_type = NodeType.JUMPDEST
                    case _:
                        start_node_type = NodeType.OTHER

                result[start_node_id] = {
                    "start": {"id": start_node_id, "type": start_node_type},
                    "end": None,
                }

                if len(nodes) >= 2:
                    end_node = nodes[-2]
                    end_node_id = end_node.split(":")[0].strip()
                    end_node_opcode = end_node.split(":")[1].strip()
                    end_node_type = NodeType.OTHER

                    match end_node_opcode:
                        case "JUMP":
                            end_node_type = NodeType.JUMP
                        case "JUMPI":
                            end_node_type = NodeType.JUMPI
                        case "JUMPDEST":
                            end_node_type = NodeType.JUMPDEST
                        case _:
                            end_node_type = NodeType.OTHER

                    result[start_node_id]["end"] = {
                        "id": end_node_id,
                        "type": end_node_type,
                    }

    return result


###########################################################
# ANALYZE FUNCTION (MAIN)
###########################################################


def analyze(filename: str) -> dict:
    # Metrics
    metrics = {
        "total_jumps": 0,
        "precisely_solved_jumps": 0,
        "soundly_solved_jumps": 0,
        "unreachable_jumps": 0,
    }

    # Retrieve the graph and the edges from the .dot file
    graph = pydot.graph_from_dot_file(filename)[0]
    edges = graph.get_edges()

    if graph is None:
        raise Exception(f"Error in reading the .dot file {filename}")

    # Classify the blocks in the graph
    # (retrieve info on the first and last node of each block)
    blocks = classify_blocks_in_out(graph)

    # Count the number of jumps and jumpis
    for block in blocks.values():
        match block["end"]["type"]:
            case NodeType.JUMP:
                metrics["total_jumps"] += 1
                # Check if the JUMP is precisely or soundly solved, or unreachable
                dests = get_dests(edges, block["start"]["id"])

                if is_unreachable(edges, block["start"]["id"]):
                    metrics["unreachable_jumps"] += 1
                elif is_precisely_solved_jump(dests, blocks):
                    metrics["precisely_solved_jumps"] += 1
                elif is_soundly_solved_jump(dests, blocks):
                    metrics["soundly_solved_jumps"] += 1
                else:
                    print(f"SPOTTED! THE JUMP AT {block['end']['id']} IS NOT SOLVED")
            case NodeType.JUMPI:
                metrics["total_jumps"] += 1
                # Check if the JUMPI is precisely or soundly solved, or unreachable
                dests = get_dests(edges, block["start"]["id"])

                if is_unreachable(edges, block["start"]["id"]):
                    metrics["unreachable_jumps"] += 1
                elif is_precisely_solved_jumpi(dests, blocks):
                    metrics["precisely_solved_jumps"] += 1
                elif is_soundly_solved_jumpi(dests, blocks):
                    metrics["soundly_solved_jumps"] += 1
                else:
                    print(f"SPOTTED! THE JUMPI AT {block['end']['id']} IS NOT SOLVED")
            case _:
                pass

    return metrics
