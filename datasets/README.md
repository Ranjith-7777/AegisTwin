# AegisArena Datasets

Only synthetic data and appropriately licensed data may be stored or referenced here. Dataset provenance, licence, intended use, and simulation boundaries must be documented before addition. Real credentials, personal data, live infrastructure details, and offensive artifacts are prohibited.

The CICIDS2017 acceptance test expects the labelled-flow files below under the
git-ignored `datasets/raw/cicids2017/` directory:

- `Monday-WorkingHours.pcap_ISCX.csv`
- `Tuesday-WorkingHours.pcap_ISCX.csv`

Obtain `GeneratedLabelledFlows.zip` through the official UNB CICIDS2017 page:
https://www.unb.ca/cic/datasets/ids-2017.html. Do not substitute the
`MachineLearningCSV.zip`/`MachineLearningCVE` layout because it omits endpoint
and timestamp fields required for provenance, correlation and projection.

