import sys
import traceback
import os
from setuptools import setup, Extension, find_packages

from distutils.command.build_ext import build_ext
from distutils.errors import (CCompilerError, DistutilsExecError,
                              DistutilsPlatformError)


def make_extensions():
    is_ci = bool(os.getenv("CI", ""))
    try:
        import numpy
    except ImportError:
        print("Installation requires `numpy`")
        raise
    try:
        import brainpy
    except ImportError:
        print("Installation requires `brainpy`, install with `python -m pip install brain-isotopic-distribution`")
        raise
    try:
        import ms_peak_picker
    except ImportError:
        print("Installation requires `ms_peak_picker`")
        raise
    try:
        from Cython.Build import cythonize
        cython_directives = {
            'embedsignature': True
        }
        macros = []
        if is_ci:
            print("CI Detected, Building With Diagnostics")
            cython_directives['linetrace'] = True
            macros.append(("CYTHON_TRACE", '1'))
        extensions = cythonize([
            Extension(name='ms_deisotope._c.scoring', sources=["ms_deisotope/_c/scoring.pyx"],
                      include_dirs=[brainpy.get_include(), ms_peak_picker.get_include(), numpy.get_include()]),
            Extension(name='ms_deisotope._c.averagine', sources=["ms_deisotope/_c/averagine.pyx"],
                      include_dirs=[brainpy.get_include()], define_macros=macros),
            Extension(name='ms_deisotope._c.deconvoluter_base', sources=["ms_deisotope/_c/deconvoluter_base.pyx"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include()], define_macros=macros),
            Extension(name='ms_deisotope._c.peak_set', sources=["ms_deisotope/_c/peak_set.pyx"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include()]),
            Extension(name='ms_deisotope._c.feature_map.lcms_feature', sources=[
                      "ms_deisotope/_c/feature_map/lcms_feature.pyx"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include()],
                      define_macros=macros),
            Extension(name='ms_deisotope._c.feature_map.feature_processor', sources=[
                      "ms_deisotope/_c/feature_map/feature_processor.pyx"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()],
                      define_macros=macros),
            Extension(name='ms_deisotope._c.feature_map.feature_map', sources=[
                      "ms_deisotope/_c/feature_map/feature_map.pyx"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()],
                      define_macros=macros),
            Extension(name='ms_deisotope._c.feature_map.feature_fit', sources=[
                      "ms_deisotope/_c/feature_map/feature_fit.pyx"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()],
                      define_macros=macros),
            Extension(name='ms_deisotope._c.feature_map.profile_transform', sources=[
                      "ms_deisotope/_c/feature_map/profile_transform.pyx"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()],
                      define_macros=macros)
        ], compiler_directives={'embedsignature': True})
    except ImportError:
        extensions = ([
            Extension(name='ms_deisotope._c.scoring', sources=["ms_deisotope/_c/scoring.c"],
                      include_dirs=[brainpy.get_include(), ms_peak_picker.get_include(), numpy.get_include()]),
            Extension(name='ms_deisotope._c.averagine', sources=["ms_deisotope/_c/averagine.c"],
                      include_dirs=[brainpy.get_include()]),
            Extension(name='ms_deisotope._c.deconvoluter_base', sources=["ms_deisotope/_c/deconvoluter_base.c"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include()]),
            Extension(name='ms_deisotope._c.peak_set', sources=["ms_deisotope/_c/peak_set.c"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include()]),
            Extension(name='ms_deisotope._c.feature_map.lcms_feature', sources=[
                      "ms_deisotope/_c/feature_map/lcms_feature.c"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include()]),
            Extension(name='ms_deisotope._c.feature_map.feature_processor', sources=[
                      "ms_deisotope/_c/feature_map/feature_processor.c"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()]),
            Extension(name='ms_deisotope._c.feature_map.feature_map', sources=["ms_deisotope/_c/feature_map/feature_map.c"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()]), 
            Extension(name='ms_deisotope._c.feature_map.feature_fit', sources=["ms_deisotope/_c/feature_map/feature_fit.c"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()]),
            Extension(name='ms_deisotope._c.feature_map.profile_transform', sources=[
                      "ms_deisotope/_c/feature_map/profile_transform.c"],
                      include_dirs=[numpy.get_include(), ms_peak_picker.get_include(), brainpy.get_include()])
        ])
    return extensions


ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError)
if sys.platform == 'win32':
    # 2.6's distutils.msvc9compiler can raise an IOError when failing to
    # find the compiler
    ext_errors += (IOError,)


def has_option(name):
    try:
        sys.argv.remove('--%s' % name)
        return True
    except ValueError:
        pass
    # allow passing all cmd line options also as environment variables
    env_val = os.getenv(name.upper().replace('-', '_'), 'false').lower()
    if env_val == "true":
        return True
    return False


class BuildFailed(Exception):

    def __init__(self):
        self.cause = sys.exc_info()[1]  # work around py 2/3 different syntax

    def __str__(self):
        return str(self.cause)


class ve_build_ext(build_ext):
    # This class allows C extension building to fail.

    def run(self):
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            traceback.print_exc()
            raise BuildFailed()

    def build_extension(self, ext):
        try:
            build_ext.build_extension(self, ext)
        except ext_errors:
            traceback.print_exc()
            raise BuildFailed()
        except ValueError:
            # this can happen on Windows 64 bit, see Python issue 7511
            traceback.print_exc()
            if "'path'" in str(sys.exc_info()[1]):  # works with both py 2/3
                raise BuildFailed()
            raise


cmdclass = {}

cmdclass['build_ext'] = ve_build_ext


def status_msgs(*msgs):
    print('*' * 75)
    for msg in msgs:
        print(msg)
    print('*' * 75)


install_requires = [
    "numpy",
    # "ms_peak_picker",
    "brain-isotopic-distribution",
    "pyteomics",
    "lxml",
]


def run_setup(include_cext=True):
    setup(
        name='ms_deisotope',
        version='0.0.2',
        packages=find_packages(),
        author=', '.join(["Joshua Klein"]),
        author_email=["jaklein@bu.edu"],
        ext_modules=make_extensions() if include_cext else None,
        cmdclass=cmdclass,
        classifiers=[
                'Development Status :: 3 - Alpha',
                'Intended Audience :: Science/Research',
                'License :: OSI Approved :: BSD License',
                'Topic :: Scientific/Engineering :: Bio-Informatics'],
        install_requires=install_requires,
        zip_safe=False)


try:
    run_setup(True)
except Exception as exc:
    run_setup(False)

    status_msgs(
        "WARNING: The C extension could not be compiled, " +
        "speedups are not enabled.",
        "Plain-Python build succeeded."
    )
