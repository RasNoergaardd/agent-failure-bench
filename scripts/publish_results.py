"""Bundle the outputs the report is computed from, for report-results/.

Run on the cluster from the repository root, where results/ and the Harbor job
directories live:

    python3 scripts/publish_results.py

It writes ~/afb-publish.tgz. The two TRAIL label files lose their free-text
`rationale` field, which paraphrases the gated TRAIL traces whose terms forbid
resharing. Nothing the agreement measures read is removed.
"""

import json
import os
import shutil
import tarfile

OUT = "/tmp/afb-publish"
JOBS = "/work3/s225786/harbor-test/jobs"

TRAIL = [
    "results/judged-trail-gaia-qwen3.8-27b-guidelines-257b897.jsonl",
    "results/judged-trail-swe_bench-qwen3.8-27b-guidelines-257b897.jsonl",
]
TERMINAL = [
    "results/judged-runs-2026-08-30-qwen3.8-27b-ctx98304.jsonl",
    "results/judged-runs-repeats-qwen3.8-27b-ctx98304.jsonl",
]
HARBOR = [
    ("full-benchmark", "2026-08-30__09-08-11"),
    ("variation", "2026-09-02__23-50-19"),
    ("sensitivity", "2026-09-08__12-28-26"),
]


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)

    for src in TRAIL:
        dst = os.path.join(OUT, os.path.basename(src))
        with open(src) as f, open(dst, "w") as g:
            for line in f:
                record = json.loads(line)
                for annotation in record.get("annotations", []):
                    annotation.pop("rationale", None)
                g.write(json.dumps(record) + "\n")
        print("stripped", os.path.basename(src))

    for src in TERMINAL:
        shutil.copy(src, OUT)
        print("copied  ", os.path.basename(src))

    for name, job in HARBOR:
        shutil.copy(os.path.join(JOBS, job, "result.json"),
                    os.path.join(OUT, "harbor-" + name + "-result.json"))
        print("copied  ", "harbor-" + name + "-result.json")

    target = os.path.expanduser("~/afb-publish.tgz")
    with tarfile.open(target, "w:gz") as tar:
        tar.add(OUT, arcname="afb-publish")
    print("wrote", target, os.path.getsize(target), "bytes")


if __name__ == "__main__":
    main()
