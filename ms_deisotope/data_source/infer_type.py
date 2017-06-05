import os
from .mzml import MzMLLoader
from .mzxml import MzXMLLoader


guessers = []
reader_types = [MzMLLoader, MzXMLLoader]


def register_type_guesser(reader_guesser):
    guessers.append(reader_guesser)
    return reader_guesser


try:
    from .thermo_raw import (
        ThermoRawLoader, infer_reader as _check_is_thermo_raw,
        register_dll as register_thermo_dll)

    reader_types.append(ThermoRawLoader)
    register_type_guesser(_check_is_thermo_raw)

except ImportError:  # pragma: no cover
    def register_thermo_dll(*args, **kwargs):
        pass


@register_type_guesser
def guess_type_from_path(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.mzml':
        return MzMLLoader
    elif ext == '.mzxml':
        return MzXMLLoader
    else:
        raise ValueError("Cannot determine ScanLoader type from file path")


@register_type_guesser
def guess_type_from_file_sniffing(file_path):
    with open(file_path, 'rb') as handle:
        header = handle.read(1000)
        if b"mzML" in header:
            return MzMLLoader
        elif b"mzXML" in header:
            return MzXMLLoader
        else:
            raise ValueError("Cannot determine ScanLoader type from header")


def guess_type(file_path):
    for guesser in guessers:
        try:
            reader_type = guesser(file_path)
            return reader_type
        except (ValueError, IOError, ImportError):
            continue
    raise ValueError("Cannot determine ScanLoader type")


def MSFileLoader(file_path, *args, **kwargs):
    """Factory function to create an object that reads scans from
    any supported data file format. Provides both iterative and
    random access.
    """
    reader_type = guess_type(file_path)
    return reader_type(file_path, *args, **kwargs)
