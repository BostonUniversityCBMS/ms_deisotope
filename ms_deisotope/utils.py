import operator
import math

from collections import defaultdict


try:
    from matplotlib import pyplot as plt
    from ms_peak_picker.utils import draw_peaklist
    has_plot = True

except ImportError:
    has_plot = False

try:
    range = xrange
except:
    range = range


def simple_repr(self):  # pragma: no cover
    template = "{self.__class__.__name__}({d})"

    def formatvalue(v):
        if isinstance(v, float):
            return "%0.4f" % v
        else:
            return str(v)

    if not hasattr(self, "__slots__"):
        d = [
            "%s=%s" % (k, formatvalue(v)) if v is not self else "(...)" for k, v in sorted(
                self.__dict__.items(), key=lambda x: x[0])
            if (not k.startswith("_") and not callable(v)) and not (v is None)]
    else:
        d = [
            "%s=%s" % (k, formatvalue(v)) if v is not self else "(...)" for k, v in sorted(
                [(name, getattr(self, name)) for name in self.__slots__], key=lambda x: x[0])
            if (not k.startswith("_") and not callable(v)) and not (v is None)]

    return template.format(self=self, d=', '.join(d))


class Base(object):
    __repr__ = simple_repr


class Constant(object):
    """A convenience type meant to be used to instantiate singletons for signaling
    specific states in return values. Similar to `None`.

    Attributes
    ----------
    name: str
        The name of the constant
    """
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self.name == str(other)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return str(self.name)

    def __nonzero__(self):
        return False


class DeconvolutionProcessResult(object):
    def __init__(self, deconvoluter, peak_set, priorities):
        self.deconvoluter = deconvoluter
        self.peak_set = peak_set
        self.priorities = priorities

    def __getitem__(self, i):
        if i == 0:
            return self.peak_set
        elif i == 1:
            return self.priorities
        else:
            raise IndexError(i)

    def __iter__(self):
        yield self.peak_set
        yield self.priorities

    def __repr__(self):
        return "DeconvolutionProcessResult(%s, %s)" % tuple(self)


class TargetedDeconvolutionResultBase(Base):
    """Base class to store all of the necessary information to retrieve the optimal
    solution for a single peak.

    Attributes
    ----------
    deconvoluter : DeconvoluterBase
        The deconvoluter to use to look up the result
    """
    def __init__(self, deconvoluter, *args, **kwargs):
        self.deconvoluter = deconvoluter

    def get(self):
        """Fetch the optimal solution after the computation has finished.

        Returns
        -------
        DeconvolutedPeak
        """
        raise NotImplementedError()


class TrivialTargetedDeconvolutionResult(TargetedDeconvolutionResultBase):
    """Stores the necessary information to retrieve the local optimal solution for
    a single peak for a deconvolution algorithm where the local optimum is the best
    solution.

    Attributes
    ----------
    query_peak : FittedPeak
        The peak queried with
    solution_peak : DeconvolutedPeak
        The optimal solution peak
    """
    def __init__(self, deconvoluter, solution_peak, query_peak, *args, **kwargs):
        super(TrivialTargetedDeconvolutionResult, self).__init__(deconvoluter, *args, **kwargs)
        self.solution_peak = solution_peak
        self.query_peak = query_peak

    def get(self):
        return self.solution_peak


def ppm_error(x, y):
    return (x - y) / y


def dict_proxy(attribute):
    """Return a decorator for a class to give it a `dict`-like API proxied
    from one of its attributes

    Parameters
    ----------
    attribute : str
        The string corresponding to the attribute which will
        be used

    Returns
    -------
    function
    """
    getter = operator.attrgetter(attribute)

    def wrap(cls):

        def __getitem__(self, key):
            return getter(self)[key]

        def __setitem__(self, key, value):
            d = getter(self)
            d[key] = value

        def keys(self):
            return getter(self).keys()

        def __iter__(self):
            return iter(getter(self))

        def items(self):
            return getter(self).items()

        cls.__getitem__ = __getitem__
        cls.__setitem__ = __setitem__
        cls.keys = keys
        cls.items = items
        cls.__iter__ = __iter__

        return cls
    return wrap


class PaddedBuffer(object):
    def __init__(self, content, start='<pad>', end="</pad>"):
        self.content = content
        self.start = start
        self.end = end
        self.position = 0
        self.diff = 0

    def read(self, n):
        if self.position < len(self.start):
            out = "".join([self.start, self.content.read(n - len(self.start))])
            self.position += n
            return out
        else:
            out = self.content.read(n)
            if len(out) < n:
                diff = n - len(out)
                if self.diff == 0:
                    self.diff = diff
                    self.position += n
                    return "".join([out, self.end[:diff]])
                else:
                    self.position += n
                    return self.end[self.diff:diff]
            else:
                self.position += n
                return out
