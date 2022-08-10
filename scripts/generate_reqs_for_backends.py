import argparse
import json
import os
import sys

from pipreqs.pipreqs import init

GLOBALLY_EXCLUDED_REQS = ["octo_pipeline_python.egg"]
GLOBALLY_INCLUDED_REQS = ["octo-pipeline-python"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--certificate-path", type=str, default=None)
    parser.add_argument("--pypi-server", type=str, default="https://pypi.python.org/simple")
    parser.add_argument("--use-local", help="Use local package info for DEV purposes only",
                        action="store_true", default=False)
    args = parser.parse_args()
    root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    backends_reqs_dir = os.path.join(root_dir, ".temp", "backends_requirements")
    scripts_dir = os.path.join(root_dir, "scripts")
    if args.certificate_path:
        os.environ["REQUESTS_CA_BUNDLE"] = args.certificate_path
    os.makedirs(backends_reqs_dir, exist_ok=True)
    backends_dir = os.path.join(root_dir, "octo_pipeline_python", "backends")
    with open(os.path.join(scripts_dir, "backends_requirements.json"), 'r') as f:
        extra_reqs = json.load(f)
    for backend_f in os.listdir(backends_dir):
        human_backend_f = backend_f.replace("_", "-")
        if os.path.isdir(os.path.join(backends_dir, backend_f)) and backend_f not in ["__pycache__"]:
            print(f"Generating reqs for backend [{backend_f}]")
            save_path = os.path.join(backends_reqs_dir, human_backend_f)
            os.makedirs(save_path, exist_ok=True)
            init({
                "<path>": os.path.join(backends_dir, backend_f),
                "--pypi-server": args.pypi_server,
                "--savepath": os.path.join(save_path, "requirements.txt"),
                "--force": True,
                "--mode": "no-pin",
                "--proxy": None,
                "--use-local": args.use_local,
                "--diff": False,
                "--clean": False,
                "--print": False
            })
            with open(os.path.join(save_path, "requirements.txt"), 'r+') as f:
                reqs = [t.strip() for t in f.readlines()]
                reqs.extend(GLOBALLY_INCLUDED_REQS)
                if human_backend_f in extra_reqs.keys():
                    reqs.extend(extra_reqs[human_backend_f].get('include', []))
                    reqs = list(filter(lambda req: req not in extra_reqs[human_backend_f].get("exclude", []) and
                                                   req not in GLOBALLY_EXCLUDED_REQS and len(req) > 0, reqs))
                else:
                    reqs = list(filter(lambda req: req not in GLOBALLY_EXCLUDED_REQS and len(req) > 0, reqs))
                print(f"Generated reqs for backend [{human_backend_f}]:")
                print(reqs)
                f.seek(0)
                f.writelines([f"{t}\n" for t in reqs])
                f.truncate()


if __name__ == "__main__":
    main()
