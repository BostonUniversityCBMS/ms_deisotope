from collections import namedtuple
import abc

from ms_peak_picker import pick_peaks
from ..averagine import neutral_mass, mass_charge_ratio
from ..utils import Constant

ScanBunch = namedtuple("ScanBunch", ["precursor", "products"])


def _repr_pretty_(scan_bunch, p, cycle):
    if cycle:
        p.text("ScanBunch(...)")
        return
    p.text("ScanBunch(\n")
    with p.group(2):
        with p.group(4, "precursor=\n"):
            p.pretty(scan_bunch.precursor)
        with p.group(4, ",\nproducts=\n"):
            p.pretty(scan_bunch.products)
    p.text(")")


ScanBunch._repr_pretty_ = _repr_pretty_


ChargeNotProvided = Constant("ChargeNotProvided")
IsolationWindowNotProvided = Constant("IsolationWindowNotProvided")


class ScanDataSource(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def _scan_arrays(self, scan):
        raise NotImplementedError()

    @abc.abstractmethod
    def _precursor_information(self, scan):
        raise NotImplementedError()

    @abc.abstractmethod
    def _scan_title(self, scan):
        raise NotImplementedError()

    @abc.abstractmethod
    def _scan_id(self, scan):
        raise NotImplementedError()

    @abc.abstractmethod
    def _scan_index(self, scan):
        raise NotImplementedError()

    @abc.abstractmethod
    def _ms_level(self, scan):
        raise NotImplementedError()

    @abc.abstractmethod
    def _scan_time(self, scan):
        raise NotImplementedError()

    @abc.abstractmethod
    def _is_profile(self, scan):
        raise NotImplementedError()


class ScanIterator(ScanDataSource):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def next(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_scan_by_id(self, scan_id):
        raise NotImplementedError()

    def _make_scan(self, data):
        return Scan(data, self)

    def __next__(self):
        return self.next()

    def __iter__(self):
        return self


class DetachedAccessError(Exception):
    pass


class DataAccessProxy(object):
    def attach(self, source):
        self.source = source

    def detach(self):
        self.source = None

    def __getstate__(self):
        return ()

    def __setstate__(self, state):
        self.source = None

    def raise_if_detached(self):
        if self.source is None:
            raise DetachedAccessError("Cannot perform operation. Instance is detached.")

    def get_scan_by_id(self, scan_id):
        self.raise_if_detached()
        return self.source.get_scan_by_id(scan_id)


class Scan(object):
    """Container for mass spectral data and associated descriptive information.

    A :class:`Scan` object is a generic object intended to be created by any `ScanDataSource` and describes
    a mass spectrum at each level of processing (Profile -> Peak Fitted -> Deconvoluted). The raw object
    provided by the source is wrapped and queried lazily when an attribute is requested, and retrieved
    using methods specific to that source type.

    Attributes
    ----------
    deconvoluted_peak_set : ms_deisotope.peak_set.DeconvolutedPeakSet or None
        Deconvoluted peaks resulting from charge state deconvolution and deisotoping. Will
        be `None` if deconvolution has not been done.
    peak_set : ms_peak_picker.peak_index.PeakIndex or None
        Picked peaks and (possibly) associated raw data points as produced by :meth:`pick_peaks`.
        Will be `None` if peak picking has not been done.
    product_scans : list
        A list of :class:`Scan` instances which were produced by fragmenting ions from this one.
    source : ScanDataSource
        The object which produced this scan and which defines the methods for retrieving common
        attributes from the underlying data structures.
    precursor_information: PrecursorInformation or None
        Descriptive metadata for the ion which was chosen for fragmentation, and a reference to
        the precursor scan
    arrays: list of numpy.ndarray
        A pair of `numpy.ndarray` objects corresponding to the raw m/z and intensity data points
    id: str
        The unique identifier for this scan as given by the source
    title: str
        The human-readable display string for this scan as shown in some external software
    ms_level: int
        The degree of fragmentation performed. 1 corresponds to a MS1 or "Survey" scan, 2 corresponds
        to MS/MS, and so on. If `ms_level` > 1, the scan is considered a "tandem scan" or "MS^n" scan
    scan_time: float
        The time the scan was acquired during data acquisition. The unit of time depends upon the source.
        May be minutes or seconds.
    index: int
        The integer number indicating how many scans were acquired prior to this scan.
    is_profile: bool
        Whether this scan's raw data points corresponds to a profile scan or whether the raw data was
        pre-centroided.
    polarity: int
        If the scan was acquired in positive mode, the value `+1`.  If the scan was acquired in negative
        mode, the value `-1`. May be used to indicating how to calibrate charge state determination methods.
    """
    def __init__(self, data, source, peak_set=None, deconvoluted_peak_set=None, product_scans=None):
        if product_scans is None:
            product_scans = []
        self.source = source
        self.peak_set = peak_set
        self.deconvoluted_peak_set = deconvoluted_peak_set

        self._data = data

        self._arrays = None
        self._id = None
        self._title = None
        self._ms_level = None
        self._scan_time = None
        self._precursor_information = None
        self._index = None
        self._is_profile = None
        self._polarity = None

        self.product_scans = product_scans

    def _load(self):
        self.arrays
        self.id
        self.title
        self.ms_level
        self.scan_time
        self.index
        self.precursor_information

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        if self.peak_set is None:
            return iter([])
        return iter(self.peak_set)

    def has_peak(self, *args, **kwargs):
        """A wrapper around :meth:`ms_peak_picker.PeakIndex.has_peak` to query the
        :class:`ms_peak_picker.FittedPeak` objects picked for this scan. If
        peaks have not yet been picked (e.g. :meth:`pick_peaks` has not been called)
        this method will return `None`

        Parameters
        ----------
        mz: float
            The m/z to search for
        error_tolerance: float
            The parts per million mass error tolerance to use

        Returns
        -------
        ms_peak_picker.FittedPeak or None
            The peak closest to the query m/z within the error tolerance window, or None if not found
            or if peaks have not yet been picked
        """
        if self.peak_set is None:
            return None
        return self.peak_set.has_peak(*args, **kwargs)

    @property
    def ms_level(self):
        if self._ms_level is None:
            self._ms_level = self.source._ms_level(self._data)
        return self._ms_level

    @property
    def is_profile(self):
        if self._is_profile is None:
            self._is_profile = self.source._is_profile(self._data)
        return self._is_profile

    @property
    def polarity(self):
        if self._polarity is None:
            self._polarity = self.source._polarity(self._data)
        return self._polarity

    @property
    def scan_time(self):
        if self._scan_time is None:
            self._scan_time = self.source._scan_time(self._data)
        return self._scan_time

    @property
    def arrays(self):
        if self._arrays is None:
            self._arrays = self.source._scan_arrays(self._data)
        return self._arrays

    @property
    def title(self):
        if self._title is None:
            self._title = self.source._scan_title(self._data)
        return self._title

    @property
    def id(self):
        if self._id is None:
            self._id = self.source._scan_id(self._data)
        return self._id

    @property
    def index(self):
        if self._index is None:
            self._index = self.source._scan_index(self._data)
        return self._index

    @property
    def precursor_information(self):
        if self.ms_level < 2:
            return None
        if self._precursor_information is None:
            self._precursor_information = self.source._precursor_information(self._data)
        return self._precursor_information

    def __repr__(self):
        return "Scan(%r, index=%d, time=%0.4f%s)" % (
            self.id, self.index, self.scan_time,
            ", " + repr(self.precursor_information) if self.precursor_information else '')

    def pick_peaks(self, *args, **kwargs):
        """A wrapper around :func:`ms_peak_picker.pick_peaks` which will populate the
        :attr:`peak_set` attribute of this scan.

        Parameters
        ----------
        *args :
            Passed along to :func:`ms_peak_picker.pick_peaks`
        **kwargs : TYPE
            Passed along to :func:`ms_peak_picker.pick_peaks`

        Returns
        -------
        self
        """
        mzs, intensities = self.arrays
        if self.is_profile:
            peak_mode = 'profile'
        else:
            peak_mode = 'centroid'

        kwargs['peak_mode'] = peak_mode

        self.peak_set = pick_peaks(mzs, intensities, *args, **kwargs)
        return self

    def pack(self):
        precursor_info = self.precursor_information
        return ProcessedScan(
            self.id, self.title, precursor_info,
            self.ms_level, self.scan_time, self.index,
            self.peak_set.pack(),
            self.deconvoluted_peak_set)


class PrecursorInformation(object):
    """Store information relating a tandem MS scan to its precursor MS scan.

    .. note:
        The attributes prefixed with `extracted_` refer to the quantities estimated
        from the data, while those unprefixed are the values read directly from the
        data source. These values regularly do not agree. When available, the extracted
        values should be more accurate.

    Attributes
    ----------
    charge : int
        The charge reported in the source metadata
    defaulted : bool
        Whether the information in the extracted fields reflects empirical
        information or fell back on the vendor-reported values.
    extracted_charge : int
        The charge estimated from the source data
    extracted_intensity : float
        The sum of the peak heights of the extracted isotopic pattern
    extracted_neutral_mass : float
        The monoisotopic neutral mass estimated from the source data
    extracted_peak : DeconvolutedPeak
        The deconvoluted peak summarizing the precursor ion
    intensity : float
        The abundance reported in the source metadata
    mz : float
        The m/z reported in the source metadata
    orphan : bool
        Whether there was an isotopic pattern to extract in the precursor scan. Usually
        paired with `defaulted`
    peak : FittedPeak
        The peak nearest `mz`, and the starting point for estimating information
        about the precursor ion
    precursor_scan_id : str
        The id string for the precursor scan
    source : ScanIteratorBase
        Any object implementing the `ScanIteratorBase` interface to be used to look up
        the precursor scan with `precursor_scan_id`
    """
    def __init__(self, mz, intensity, charge, precursor_scan_id=None, source=None,
                 extracted_neutral_mass=0, extracted_charge=0, extracted_intensity=0,
                 peak=None, extracted_peak=None, defaulted=False, orphan=False):
        self.mz = mz
        self.intensity = intensity
        self.charge = charge

        self.precursor_scan_id = precursor_scan_id
        self.source = source

        self.extracted_neutral_mass = extracted_neutral_mass
        self.extracted_charge = extracted_charge
        self.extracted_intensity = extracted_intensity

        self.peak = peak
        self.extracted_peak = extracted_peak
        self.defaulted = defaulted
        self.orphan = orphan

    def __repr__(self):
        return "PrecursorInformation(mz=%0.4f/%0.4f, intensity=%0.4f/%0.4f, charge=%d/%d, scan_id=%r)" % (
            self.mz,
            mass_charge_ratio(self.extracted_neutral_mass, self.extracted_charge if self.extracted_charge != 0 else 1)
            if self.extracted_neutral_mass != 0. else 0.,
            self.intensity, self.extracted_intensity or 0., self.charge,
            self.extracted_charge or 0., self.precursor_scan_id)

    def __getstate__(self):
        return (self.mz, self.intensity, self.charge, self.precursor_scan_id, None, self.extracted_neutral_mass,
                self.extracted_charge, self.extracted_intensity, self.peak, self.extracted_peak)

    def __setstate__(self, state):
        (self.mz, self.intensity, self.charge, self.precursor_scan_id, self.source, self.extracted_neutral_mass,
         self.extracted_charge, self.extracted_intensity, self.peak, self.extracted_peak) = state

    def extract(self, peak, override_charge=None):
        self.extracted_neutral_mass = peak.neutral_mass
        self.extracted_charge = int(peak.charge) if override_charge is None else override_charge
        self.extracted_intensity = peak.intensity
        self.extracted_peak = peak

    def default(self):
        self.extracted_neutral_mass = self.neutral_mass
        self.extracted_charge = int(self.charge)
        self.extracted_intensity = self.intensity
        self.defaulted = True

    @property
    def neutral_mass(self):
        return neutral_mass(self.mz, self.charge)

    @property
    def extracted_mz(self):
        return mass_charge_ratio(self.extracted_neutral_mass, self.extracted_charge)

    @property
    def precursor(self):
        return self.source.get_scan_by_id(self.precursor_scan_id)


class ProcessedScan(object):
    def __init__(self, id, title, precursor_information, ms_level, scan_time, index, peak_set, deconvoluted_peak_set):
        self.id = id
        self.title = title
        self.precursor_information = precursor_information
        self.ms_level = ms_level
        self.scan_time = scan_time
        self.index = index
        self.peak_set = peak_set
        self.deconvoluted_peak_set = deconvoluted_peak_set

    def __iter__(self):
        return iter(self.deconvoluted_peak_set)

    def __getitem__(self, index):
        return self.deconvoluted_peak_set[index]

    def __repr__(self):
        return "ProcessedScan(id=%s, ms_level=%d, %d peaks)" % (self.id, self.ms_level, len(self.deconvoluted_peak_set))
