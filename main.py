import argparse
import logging
import random
import csv
import json
import chardet
import os
import sys

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


def inject_noise(value, noise_level, fallback_scale=0.0):
    """
    Injects random noise into a numerical value.
    """
    try:
        value = float(value)  # Attempt to convert to float
        if value == 0:
            # Scaling the draw by the value itself leaves zero at zero
            # at any noise level. Draw from the column or file range
            # instead, or from a unit scale of 1.0 when that range is
            # zero as well.
            scale = fallback_scale if fallback_scale > 0 else 1.0
            noise = random.uniform(-noise_level * scale, noise_level * scale)
        else:
            noise = random.uniform(-noise_level * value, noise_level * value)
        return value + noise
    except (ValueError, TypeError):
        # If the value is not a number, return it unchanged
        return value


def process_csv(input_file, output_file, noise_level, encoding):
    """
    Processes a CSV file, injecting noise into numerical fields.
    """
    # The whole input is read before the output is opened. An empty file
    # used to fail on the header read after the output had already been
    # created, leaving a zero byte file that looked like a result.
    with open(input_file, 'r', encoding=encoding) as infile:
        rows = list(csv.reader(infile))
    if not rows:
        raise ValueError(f"CSV file is empty: {input_file}")

    # Per column numeric range, used as the noise scale for zero cells.
    col_ranges = {}
    for row in rows[1:]:
        for idx, cell in enumerate(row):
            try:
                num = float(cell)
            except (ValueError, TypeError):
                continue
            lo, hi = col_ranges.get(idx, (num, num))
            col_ranges[idx] = (min(lo, num), max(hi, num))

    noised = 0

    def noise_cell(idx, cell):
        nonlocal noised
        try:
            float(cell)
        except (ValueError, TypeError):
            return cell
        noised += 1
        lo, hi = col_ranges.get(idx, (0.0, 0.0))
        return inject_noise(cell, noise_level, hi - lo)

    out_rows = [[noise_cell(idx, cell) for idx, cell in enumerate(row)]
                for row in rows[1:]]

    if noised == 0:
        logging.error("No values noised: the file contains no numeric values.")
        raise ValueError("No values noised.")

    with open(output_file, 'w', newline='', encoding=encoding) as outfile:
        writer = csv.writer(outfile)
        writer.writerow(rows[0])  # Write the header row
        writer.writerows(out_rows)

    logging.info(f"Noised {noised} values.")
    logging.info(f"Successfully processed CSV file: {input_file}")


def process_json(input_file, output_file, noise_level, encoding):
    """
    Processes a JSON file, injecting noise into numerical fields.
    """
    try:
        with open(input_file, 'r', encoding=encoding) as infile:
            data = json.load(infile)

        # File wide numeric range, used as the noise scale for zeros.
        numbers = []

        def collect(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    collect(v)
            elif isinstance(obj, list):
                for item in obj:
                    collect(item)
            elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
                numbers.append(float(obj))

        collect(data)
        file_range = (max(numbers) - min(numbers)) if numbers else 0.0

        noised = 0

        def process_data(obj):
            nonlocal noised
            if isinstance(obj, dict):
                return {k: process_data(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [process_data(item) for item in obj]
            else:
                # Only real numbers take noise. float(True) is 1.0, so
                # routing a JSON boolean through inject_noise silently
                # rewrote it as a noisy float and changed the value's type.
                if isinstance(obj, bool) or obj is None or isinstance(obj, str):
                    return obj
                noised += 1
                return inject_noise(obj, noise_level, file_range)

        noisy_data = process_data(data)

        if noised == 0:
            logging.error("No values noised: the file contains no numeric values.")
            raise ValueError("No values noised.")

        with open(output_file, 'w', encoding=encoding) as outfile:
            json.dump(noisy_data, outfile, indent=4)

        logging.info(f"Noised {noised} values.")
        logging.info(f"Successfully processed JSON file: {input_file}")

    except FileNotFoundError:
        logging.error(f"Input file not found: {input_file}")
        raise
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in file: {input_file}")
        raise
    except Exception as e:
        logging.error(f"Error processing JSON file: {e}")
        raise


def main():
    """
    Main function to parse arguments, detect file type, and process the input file.
    """
    args = setup_argparse()

    input_file = args.input_file
    output_file = args.output_file
    noise_level = args.noise_level

    # Input validation
    if not (0 < noise_level <= 1):
        logging.error("Noise level must be greater than 0 and at most 1.")
        sys.exit(1)

    if not os.path.exists(input_file):
        logging.error(f"Input file '{input_file}' does not exist.")
        sys.exit(1)

    # Refuse to overwrite the input, under any spelling of the path.
    if os.path.realpath(input_file) == os.path.realpath(output_file):
        logging.error("Output file must differ from the input file.")
        sys.exit(1)

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
            sys.exit(1)
    if file_type not in ["csv", "json"]:
        logging.error("Invalid file type. Choose 'csv' or 'json'.")
        sys.exit(1)

    # Process the file
    try:
        if file_type == "csv":
            process_csv(input_file, output_file, noise_level, encoding)
        elif file_type == "json":
            process_json(input_file, output_file, noise_level, encoding)
    except Exception:
        sys.exit(1)

if __name__ == "__main__":
    main()