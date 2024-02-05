###########################################################
# Python to run EtherSolve.jar given the file containing the bytecode
# of the contract and the output directory.
###########################################################

import os


def run(bytecode_file: str, output_dir: str):
    # Check if the output dir exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Extract filename without extension and parent directory
    result_filename = os.path.basename(bytecode_file).split(".")[0]

    # Run EtherSolve.jar
    os.system(
        f"java -jar EtherSolve.jar -rd {bytecode_file} -o {output_dir}/{result_filename}.dot"
    )
    
    # Check if the .dot file has been created
    if not os.path.exists(f"{output_dir}/{result_filename}.dot"):
        raise Exception(f"Error in running EtherSolve.jar for {bytecode_file}")
