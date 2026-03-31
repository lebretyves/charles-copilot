"""Waveform dataset schemas, labels, and segmentation helpers."""

from .features import CaseFrameCache, compute_signal_feature_set, extract_feature_record
from .labels import LABEL_TAXONOMY, infer_weak_labels
from .schemas import (
    DatasetPaths,
    DatasetSource,
    FeatureRecord,
    SegmentRecord,
    SegmentSpec,
    SignalFeatureSet,
    SignalSpec,
    VitalDBDatasetManifest,
    WindowSignalStats,
)
from .segmenter import (
    DEFAULT_MANIFEST_PATH,
    build_waveform_file_map,
    find_case_files,
    iter_case_segments,
    load_dataset_manifest,
    resolve_manifest_paths,
)

__all__ = [
    "CaseFrameCache",
    "FeatureRecord",
    "DEFAULT_MANIFEST_PATH",
    "LABEL_TAXONOMY",
    "DatasetPaths",
    "DatasetSource",
    "SegmentRecord",
    "SegmentSpec",
    "SignalFeatureSet",
    "SignalSpec",
    "VitalDBDatasetManifest",
    "WindowSignalStats",
    "build_waveform_file_map",
    "compute_signal_feature_set",
    "extract_feature_record",
    "find_case_files",
    "infer_weak_labels",
    "iter_case_segments",
    "load_dataset_manifest",
    "resolve_manifest_paths",
]
