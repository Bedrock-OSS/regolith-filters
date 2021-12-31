import json
import sys
from itertools import chain
from pathlib import Path
from typing import Dict, List, Type, Union

REALITY_PATH = Path("")
EXPECTATIONS_PATH = Path("data/filter_tester")

def print_red(text):
    for t in text.split('\n'):
        print("\033[91m {}\033[00m".format(t))

class FilterTesterException(Exception):
    pass

JSON = Union[Dict, List, str, int, float, bool, Type[None]]

def json_path_to_str(json_path: List[Union[int, str]]) -> str:
    return f'[{"->".join(str(i) for i in json_path)}]'

def assert_eq_json(
        reality: JSON, expectations: JSON, json_path: List[str]=None) -> None:
    '''
    Compares the content of two JSON objects. If they are not equal, an
    FilterTesterException is raised.
    '''
    if json_path is None:
        json_path = []
    if reality == expectations:
        return
    elif type(reality) != type(expectations):
        raise FilterTesterException(
            f"Type mismatch at {json_path_to_str(json_path)}: "
            f"{reality} != {expectations}")
    elif isinstance(reality, dict):
        assert_eq_dict(reality, expectations, json_path)
    elif isinstance(reality, list):
        assert_eq_list(reality, expectations, json_path)
    elif reality != expectations:
        raise FilterTesterException(
            f"Value mismatch at {json_path_to_str(json_path)}: "
            f"{reality} != {expectations}")

def assert_eq_dict(
        reality: Dict, expectations: Dict, json_path: List[str]) -> None:
    '''
    Asserts that two JSON dictionaries are equal.
    '''
    reality_keys = set(reality.keys())
    expectations_keys = set(expectations.keys())
    if reality_keys != expectations_keys:
        surplus_keys = reality_keys - expectations_keys
        missing_keys = expectations_keys - reality_keys
        error = [f"JSON keys mismatch at {json_path_to_str(json_path)}"]
        if surplus_keys:
            error.append(f"    Unexpected keys: {', '.join(surplus_keys)}")
        if missing_keys:
            error.append(f"    Missing keys: {', '.join(missing_keys)}")
        raise FilterTesterException("\n".join(error))
    for key in reality_keys:
        assert_eq_json(reality[key], expectations[key], json_path + [key])

def assert_eq_list(
        reality: List, expectations: List, json_path: List[str]) -> None:
    '''
    Asserts that two JSON lists are equal.
    '''
    if len(reality) != len(expectations):
        raise FilterTesterException(
            f"JSON list length mismatch at {json_path_to_str(json_path)}, "
            f"expected {len(expectations)} elements, got {len(reality)}")
    for i in range(len(reality)):
        assert_eq_json(reality[i], expectations[i], json_path + [i])

def main(errors_stop_execution: bool):
    reality_files = set(chain(
        [i.relative_to(REALITY_PATH) for i in REALITY_PATH.glob("RP/**/*")],
        [i.relative_to(REALITY_PATH) for i in REALITY_PATH.glob("BP/**/*")]))
    expectations_files = set(chain(
        [i.relative_to(EXPECTATIONS_PATH) for i in EXPECTATIONS_PATH.glob("RP/**/*")],
        [i.relative_to(EXPECTATIONS_PATH) for i in EXPECTATIONS_PATH.glob("BP/**/*")])
    )
    errors = []
    if expectations_files != reality_files:
        surplus_files = reality_files - expectations_files
        missing_files = expectations_files - reality_files
        error = [f"Files mismatch:"]
        if surplus_files:
            error.append(
                f"    Unexpected files: "
                f"{', '.join(i.as_posix() for i in surplus_files)}")
        if missing_files:
            error.append(
                f"    Missing files: "
                f"{', '.join(i.as_posix() for i in missing_files)}")
        errors.append(FilterTesterException("\n".join(error)))
    common_files = expectations_files & reality_files

    def compare_binary_files(file: Path) -> None:
        with open(REALITY_PATH / file, "rb") as f:
            reality = f.read()
        with open(EXPECTATIONS_PATH / file, "rb") as f:
            expectations = f.read()
        if reality != expectations:
            errors.append(FilterTesterException(
                f"File mismatch at {file.as_posix()}"))

    for file in common_files:
        if (REALITY_PATH / file).is_dir() ^ (EXPECTATIONS_PATH / file).is_dir():
            errors.append(FilterTesterException(
                f"File mismatch at {file.as_posix()}"))
        if (REALITY_PATH / file).is_dir():
            continue  # Both are directories, so we don't need to compare them
        if file.suffix == ".json":  # JSON is a special case
            try:
                with open(REALITY_PATH / file, "r") as f:
                    reality = json.load(f)
                with open(EXPECTATIONS_PATH / file, "r") as f:
                    expectations = json.load(f)
                try:
                    assert_eq_json(reality, expectations)
                except FilterTesterException as e:
                    errors.append(FilterTesterException(
                        f"File mismatch at {file.as_posix()}:" + str(e)))
            except Exception as e:  # Compare files like binary files
                raise Exception() from e
                compare_binary_files(file)
        else:
            compare_binary_files(file)
    if errors:
        for error in errors:
            print_red(str(error))
        if errors_stop_execution:
            sys.exit(1)

if __name__ == "__main__":
    try:
        config = json.loads(sys.argv[1])
    except Exception:
        config = {}
    errors_stop_execution = config.get("errors_stop_execution", False)
    main(errors_stop_execution)
