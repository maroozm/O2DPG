#!/usr/bin/env python3

#
# Analsysis task functionality
#
# --> to inject analysis tasks into an existing workflow <--
#
# From another script one can call (example taken from the o2dpg_sim_workflow)
# add_analysis_tasks(workflow["stages"], needs=[AOD_merge_task["name"]], is_mc=True))
#
# --> create a stand-alone workflow file with only analyses <--
#
# Help message:
# usage: o2dpg_analysis_test_workflow.py [-h] -f INPUT_FILE [-a ANALYSIS_DIR] [-o OUTPUT] [--is-mc] [--with-qc-upload] [--run-number RUN_NUMBER] [--pass-name PASS_NAME] [--period-name PERIOD_NAME] [--config CONFIG] [--only-analyses [ONLY_ANALYSES [ONLY_ANALYSES ...]]]
#
# Create analysi test workflow
#
# optional arguments:
#   -h, --help            show this help message and exit
#   -f INPUT_FILE, --input-file INPUT_FILE
#                         full path to the AO2D input
#   -a ANALYSIS_DIR, --analysis-dir ANALYSIS_DIR
#                         the analysis output and working directory
#   -o OUTPUT, --output OUTPUT
#                         the workflow file name
#   --is-mc               whether the input comes from MC (data assumed otherwise)
#   --with-qc-upload
#   --run-number RUN_NUMBER
#                         the run number
#   --pass-name PASS_NAME
#                         pass name
#   --period-name PERIOD_NAME
#                         prodcution tag
#   --config CONFIG       overwrite the default config JSON. Pass as </path/to/file>, will be automatically configured to json://
#   --only-analyses [ONLY_ANALYSES [ONLY_ANALYSES ...]]
#                         filter only on these analyses
#
# Only the -f/--input-file argument is required in both cases, MC or data
# If run --with-upload-qc is enabled, --period-name is required as well; in addition, when running on data, also --pass-name is required; for MC that is set to passMC
#
# Example for data
# 1. o2dpg_analysis_test_workflow.py -f </path/to/AO2D.root>
# This constructs all analysis workflows compatible with data
# 2. o2dpg_analysis_test_workflow.py -f </path/to/AO2D.root> --with-qc-upload --pass-name <some-pass-name> --period-name <some-period-name>
# This in addition adds tasks to upload data the analysis results to the CCDB
# 3. o2dpg_analysis_test_workflow.py -f </path/to/AO2D.root> --only-analyses MCHistograms EventTrackQA EventSelectionQA
# Filter only desired analyses. NOTE in this case: The analysis MCHistograms would automatically be taken out again by the script since it is not compatible with data
#
# Of course one if free to combine the above arguments
#
# If run on MC, just pass the flag --is-mc
#
# Now it is time to run the workflow
#
# ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json
#
# If your analyses are embedded in a wider workflow (e.g. one created with o2dpg_sim_workflow) you can do
# 1. ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json --target-labels Analysis
# to run everything which is labelled with "Analysis" (which would basically be all analyses)
# 2. ${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py -f workflow.json -tt Analysis_<ana_name>
# to run only this specific analysis
#
import sys
import importlib.util
import argparse
from os import environ
from os.path import join, exists, abspath, expanduser
import json

# make sure O2DPG + O2 is loaded
O2DPG_ROOT=environ.get('O2DPG_ROOT')

if O2DPG_ROOT is None:
    print('ERROR: This needs O2DPG loaded')
    sys.exit(1)

# dynamically import required utilities
module_name = "o2dpg_workflow_utils"
spec = importlib.util.spec_from_file_location(module_name, join(O2DPG_ROOT, "MC", "bin", "o2dpg_workflow_utils.py"))
o2dpg_workflow_utils = importlib.util.module_from_spec(spec)
sys.modules[module_name] = o2dpg_workflow_utils
spec.loader.exec_module(o2dpg_workflow_utils)
from o2dpg_workflow_utils import createTask, dump_workflow

#######################
# ANALYSIS definition #
#######################

# some commong definitions
ANALYSIS_LABEL = "Analysis"
ANALYSIS_LABEL_ON_MC = f"{ANALYSIS_LABEL}MC"
ANALYSIS_VALID_MC = "mc"
ANALYSIS_VALID_DATA = "data"


def full_ana_name(raw_ana_name):
    """Make the standard name of the analysis how it should appear in the workflow"""
    return f"{ANALYSIS_LABEL}_{raw_ana_name}"


def create_ana_task(name, cmd, output_dir, *, needs=None, shmsegmentsize="--shm-segment-size 2000000000",
                    aodmemoryratelimit="--aod-memory-rate-limit 500000000",
                    readers="--readers 1", extraarguments="-b", is_mc=False):
    """Quick helper to create analysis task

    This creates an analysis task from various arguments

    Args:
        name: str
            desired analysis name
        cmd: str
            command line to run
        output_dir: str
            analysis output and work directory
    Keyword args (optional):
        needs: tuple, list
            list of other tasks to be run before
        shmsegmentsize: str
            O2/DPL argument string for shared mem size
        aodmemoryratelimit: str
            O2/DPL argument string for AOD memory rate limit
        readers: O2/DPL argument string
            number of readers
        extraarguments: str
            O2/DPL argument string for any other desired arguments to be added to the executed cmd
    Return:
        dict: the task dictionary
    """
    # if another workflow want to use it from the outside, allow to inject dependencies before analyses can be run
    if needs is None:
        # set to empty list
        needs = []
    task = createTask(name=full_ana_name(name), cwd=join(output_dir, name), lab=[ANALYSIS_LABEL, name], cpu=1, mem='2000', needs=needs)
    if is_mc:
        task["labels"].append(ANALYSIS_LABEL_ON_MC)
    task['cmd'] = f"{cmd} {shmsegmentsize} {aodmemoryratelimit} {readers} {extraarguments}"
    return task


def load_analyses(analyses_only=None, include_disabled_analyses=False):
    analyses_config = join(O2DPG_ROOT, "MC", "config", "analysis_testing", "json", "analyses_config.json")
    with open (analyses_config, "r") as f:
        analyses_config = json.load(f)["analyses"]

    collect_analyses = []
    for ana in analyses_config:
        if analyses_only and ana["name"] not in analyses_only:
            continue
        if not ana.get("enabled", False) and not include_disabled_analyses:
            print(f"INFO: Analysis {ana['name']} not added since it is disabled")
            continue
        collect_analyses.append(ana)

    return collect_analyses


def add_analysis_post_processing_tasks(workflow):
    """add post-processing step to analysis tasks if possible

    Args:
        workflow: list
            current list of tasks
    """
    analyses_to_add_for = {}
    # collect analyses in current workflow
    for task in workflow:
        if ANALYSIS_LABEL in task["labels"]:
            analyses_to_add_for[task["name"]] = task

    for ana in load_analyses(include_disabled_analyses=True):
        if not ana["expected_output"]:
            continue
        ana_name_raw = ana["name"]
        post_processing_macro = join(O2DPG_ROOT, "MC", "analysis_testing", "post_processing", f"{ana_name_raw}.C")
        if not exists(post_processing_macro):
            continue
        ana_name = full_ana_name(ana_name_raw)
        if ana_name not in analyses_to_add_for:
            continue
        pot_ana = analyses_to_add_for[ana_name]
        cwd = pot_ana["cwd"]
        needs = [ana_name]
        task = createTask(name=f"{ANALYSIS_LABEL}_post_processing_{ana_name_raw}", cwd=join(cwd, "post_processing"), lab=[ANALYSIS_LABEL, f"{ANALYSIS_LABEL}PostProcessing", ana_name_raw], cpu=1, mem='2000', needs=needs)
        input_files = ",".join([f"../{eo}" for eo in ana["expected_output"]])
        cmd = f"\\(\\\"{input_files}\\\",\\\"./\\\"\\)"
        task["cmd"] = f"root -l -b -q {post_processing_macro}{cmd}"
        workflow.append(task)


def add_analysis_tasks(workflow, input_aod="./AO2D.root", output_dir="./Analysis", *, analyses_only=None, is_mc=True, needs=None, autoset_converters=False, include_disabled_analyses=False, timeout=None):
    """Add default analyses to user workflow

    Args:
        workflow: list
            list of tasks to add the analyses to
        input_aod: str
            path to AOD to be analysed
        output_dir: str
            top-level output directory under which the analysis is executed and potential results are saved
    Keyword arguments:
        analyses_only: iter (optional)
            pass iterable of analysis names so only those will be considered
        is_mc: bool
            whether or not MC is expected, otherwise data is assumed
        needs: iter (optional)
            if specified, list of other tasks which need to be run before
    """

    additional_workflows = []
    if not input_aod.startswith("alien://"):
        input_aod = abspath(input_aod)
        if autoset_converters: # This is needed to run with the latest TAG of the O2Physics with the older data
            if input_aod.endswith(".root"):
                from ROOT import TFile
                froot = TFile.Open(input_aod, "READ")
                found_O2collision_001 = False
                for i in froot.GetListOfKeys():
                    if "DF_" not in i.GetName():
                        continue
                    df_dir = froot.Get(i.GetName())
                    # print(i)
                    for j in df_dir.GetListOfKeys():
                        # print(j)
                        if "O2collision_001" in j.GetName():
                            found_O2collision_001 = True
                    if not found_O2collision_001:
                        additional_workflows.append("o2-analysis-collision-converter --doNotSwap")
                    break
    if input_aod.endswith(".txt") and not input_aod.startswith("@"):
        input_aod = f"@{input_aod}"

    data_or_mc = ANALYSIS_VALID_MC if is_mc else ANALYSIS_VALID_DATA

    for ana in load_analyses(analyses_only, include_disabled_analyses=include_disabled_analyses):
        configuration = ana.get("config", {}).get(data_or_mc, None)
        if not configuration:
            print(f"INFO: Analysis {ana['name']} not added since no configuration found for {data_or_mc}")
            continue
        # sanitize path
        configuration = configuration.replace("json://", "")
        if configuration[0] != "$":
            # only do this if there is no potential environment variable given as the first part of the path
            configuration = abspath(expanduser(configuration))
        configuration = f"json://{configuration}"

        for i in additional_workflows:
            if i not in ana["tasks"]:
                # print("Appending extra task", i, "to analysis", ana["name"], "as it is not there yet and needed for conversion")
                ana["tasks"].append(i)
        piped_analysis = f" --configuration {configuration} | ".join(ana["tasks"])
        piped_analysis += f" --configuration {configuration} --aod-file {input_aod}"
        if timeout is not None:
            piped_analysis += f" --timeout {timeout}"
        workflow.append(create_ana_task(ana["name"], piped_analysis, output_dir, needs=needs, is_mc=is_mc))

    # append potential post-processing
    add_analysis_post_processing_tasks(workflow)


def add_analysis_qc_upload_tasks(workflow, period_name, run_number, pass_name):
    """add o2-qc-upload-root-objects to specified analysis tasks

    The analysis name has simply to be present in the workflow. Then adding these upload tasks works
    for any analysis because it does not have to have any knowledge about the analysis.

    Args:
        workflow: list
            current list of tasks
        ana_tasks_expected_outputs: list of tuples
            [(AnalysisName_1, (expected_output_1_1, expected_output_1_2, ...)), ..., (AnalysisName_N, (expected_output_N_1, expected_output_N_2, ...)) ]
    """
    analyses_to_add_for = {}
    # collect analyses in current workflow
    for task in workflow:
        if ANALYSIS_LABEL in task["labels"]:
            analyses_to_add_for[task["name"]] = task

    for ana in load_analyses(include_disabled_analyses=True):
        if not ana["expected_output"]:
            continue
        ana_name_raw = ana["name"]
        ana_name = full_ana_name(ana_name_raw)
        if ana_name not in analyses_to_add_for:
            continue
        # search through workflow stages if we can find the requested analysis
        pot_ana = analyses_to_add_for[ana_name]
        cwd = pot_ana["cwd"]
        qc_tag = f"Analysis{ana_name_raw}"
        needs = [ana_name]
        provenance = "qc_mc" if ANALYSIS_LABEL_ON_MC in pot_ana["labels"] else "qc"
        for eo in ana["expected_output"]:
            # this seems unnecessary but to ensure backwards compatible behaviour...
            rename_output = eo.strip(".root")
            rename_output = f"{rename_output}_{ana_name_raw}.root"
            # add upload task for each expected output file
            task = createTask(name=f"{ANALYSIS_LABEL}_finalize_{ana_name_raw}_{rename_output}", cwd=cwd, lab=[f"{ANALYSIS_LABEL}Upload", ana_name_raw], cpu=1, mem='2000', needs=needs)
            # This has now to be renamed for upload, as soon as that is done, the output is renamed back to its original, there is in general no point of renaming it on disk only because one specific tasks needs a renamed version of it
            rename_cmd = f"mv {eo} {rename_output}"
            rename_back_cmd = f"mv {rename_output} {eo}"
            task["cmd"] = f"{rename_cmd} && o2-qc-upload-root-objects --input-file ./{rename_output} --qcdb-url ccdb-test.cern.ch:8080 --task-name Analysis{ana_name_raw} --detector-code AOD --provenance {provenance} --pass-name {pass_name} --period-name {period_name} --run-number {run_number} && {rename_back_cmd} "
            workflow.append(task)


def run(args):
    """digesting what comes from the command line"""
    if args.with_qc_upload and (not args.pass_name or not args.period_name):
        print("ERROR: QC upload was requested, however in that case a --pass-name and --period-name are required")
        return 1

    workflow = []
    add_analysis_tasks(workflow, args.input_file, expanduser(args.analysis_dir), is_mc=args.is_mc, analyses_only=args.only_analyses, autoset_converters=args.autoset_converters, include_disabled_analyses=args.include_disabled, timeout=args.timeout)
    if args.with_qc_upload:
        add_analysis_qc_upload_tasks(workflow, args.period_name, args.run_number, args.pass_name)
    if not workflow:
        print("WARNING: Nothing was added")
    dump_workflow(workflow, args.output)
    print("Now you can run the workflow e.g.", "`${O2DPG_ROOT}/MC/bin/o2_dpg_workflow_runner.py" + f" -f {args.output}`")
    return 0


def main():
    """entry point when run directly from command line"""
    parser = argparse.ArgumentParser(description='Create analysis test workflow')
    parser.add_argument("-f", "--input-file", dest="input_file", default="./AO2D.root", help="full path to the AO2D input", required=True)
    parser.add_argument("-a", "--analysis-dir", dest="analysis_dir", default="./Analysis", help="the analysis output and working directory")
    parser.add_argument("-o", "--output", default="workflow_analysis_test.json", help="the workflow file name")
    parser.add_argument("--is-mc", dest="is_mc", action="store_true", help="whether the input comes from MC (data assumed otherwise)")
    parser.add_argument("--with-qc-upload", dest="with_qc_upload", action="store_true")
    parser.add_argument("--run-number", dest="run_number", type=int, default=300000, help="the run number")
    parser.add_argument("--pass-name", dest="pass_name", help="pass name")
    parser.add_argument("--period-name", dest="period_name", help="period name")
    parser.add_argument("--only-analyses", dest="only_analyses", nargs="*", help="filter only on these analyses")
    parser.add_argument("--include-disabled", dest="include_disabled", action="store_true", help="ignore if an analysis is disabled an run anyway")
    parser.add_argument("--autoset-converters", dest="autoset_converters", action="store_true", help="Compatibility mode to automatically set the converters for the analysis")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout for analysis tasks in seconds.")
    parser.set_defaults(func=run)
    args = parser.parse_args()
    return(args.func(args))

if __name__ == "__main__":
    sys.exit(main())
