import argparse
import logging
import random
import csv
import json
import chardet
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.
    """
    parser = argparse.ArgumentParser(
        description="Inserts random, statistically insignificant noise into numerical data fields."
    )

    parser.add_argument("input_file", help="Path to the input file (CSV or JSON).")
    parser.add_argument("output_file", help="Path to the output file.")
    parser.add_argument(
        "--noise_level",
        type=float,
        default=0.01,
        help="Percentage of noise to add (e.g., 0.01 for 1%%). Default: 0.01",
    )
    parser.add_argument(
        "--file_type",
        choices=["csv", "json"],
        help="Specify the file type (csv or json). If not provided, it will be automatically detected.",
    )
    parser.add_argument(
        "--encoding",
        type=str,
        default=None,
        help="Specify the encoding of the input file. If not provided, it will be automatically detected.",
    )

    return parser.parse_args()


def detect_file_encoding(file_path):
    """
    Detects the encoding of a file.
    """
    try:
        with open(file_path, 'rb') as f:
            result = chardet.detect(f.read())
            return result['encoding']
    except Exception as e:
        logging.error(f"Error detecting file encoding: {e}")
        return None


def inject_noise(value, noise_level):
    """
    Injects random noise into a numerical value.
    """
    try:
        value = float(value)  # Attempt to convert to float
        noise = random.uniform(-noise_level * value, noise_level * value)
        return value + noise
    except (ValueError, TypeError):
        # If the value is not a number, return it unchanged
        return value


def process_csv(input_file, output_file, noise_level, encoding):
    """
    Processes a CSV file, injecting noise into numerical fields.
    """
    try:
        with open(input_file, 'r', encoding=encoding) as infile, \
             open(output_file, 'w', newline='', encoding=encoding) as outfile:

            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            header = next(reader)
            writer.writerow(header)  # Write the header row

            for row in reader:
                new_row = [inject_noise(cell, noise_level) for cell in row]
                writer.writerow(new_row)

        logging.info(f"Successfully processed CSV file: {input_file}")

    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
    except Exception as e:
        logging.error(f"Error processing CSV file: {e}")


def process_json(input_file, output_file, noise_level, encoding):
    """
    Processes a JSON file, injecting noise into numerical fields.
    """
    try:
        with open(input_file, 'r', encoding=encoding) as infile:
            data = json.load(infile)

        def process_data(obj):
            if isinstance(obj, dict):
                return {k: process_data(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [process_data(item) for item in obj]
            else:
                return inject_noise(obj, noise_level)

        noisy_data = process_data(data)

        with open(output_file, 'w', encoding=encoding) as outfile:
            json.dump(noisy_data, outfile, indent=4)

        logging.info(f"Successfully processed JSON file: {input_file}")

    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in file: {input_file}")
    except Exception as e:
        logging.error(f"Error processing JSON file: {e}")


def main():
    """
    Main function to parse arguments, detect file type, and process the input file.
    """
    args = setup_argparse()

    input_file = args.input_file
    output_file = args.output_file
    noise_level = args.noise_level

    # Input validation
    if not (0 <= noise_level <= 1):
        logging.error("Noise level must be between 0 and 1.")
        return

    if not os.path.exists(input_file):
        logging.error(f"Input file '{input_file}' does not exist.")
        return

    # Determine encoding
    encoding = args.encoding
    if encoding is None:
        encoding = detect_file_encoding(input_file)
        if encoding is None:
            logging.warning("Failed to detect encoding. Using default 'utf-8'.")
            encoding = 'utf-8'
        else:
            logging.info(f"Detected encoding: {encoding}")

    # Determine file type
    file_type = args.file_type
    if file_type is None:
        if input_file.lower().endswith(".csv"):
            file_type = "csv"
        elif input_file.lower().endswith(".json"):
            file_type = "json"
        else:
            logging.error("Could not automatically determine file type. Please specify using --file_type.")
            return
    if file_type not in ["csv", "json"]:
        logging.error("Invalid file type. Choose 'csv' or 'json'.")
        return

    # Process the file
    if file_type == "csv":
        process_csv(input_file, output_file, noise_level, encoding)
    elif file_type == "json":
        process_json(input_file, output_file, noise_level, encoding)

if __name__ == "__main__":
    main()