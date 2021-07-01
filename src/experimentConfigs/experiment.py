# This experiment file it is quite heavy on loading considering
# the imported packages
import datetime as dt
import enum
import json
import os
import sys
from typing import Tuple

import hyperopt
import hyperopt.pyll
import numpy as np
from datasets import list_metrics

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from models.Model import ModelConstruction
from models.transformersModel import TransformersModel


# Here are the possible model
# types denoted
class ModelType(enum.Enum):
    transformers = "transformers"
    bagOfWords2LayerModel = "BagOfWords2LayerModel"


class TokenizerType(enum.Enum):
    transformers = "transformers"


def report(info: dict, reportPath: str):
    """ This function adds a report of an experiment to a json report file.
    The final reported experiment is presented in an html file in github.

    Args:
        reportPath (str): The json file to write or append the report to.
    """
    if not os.path.exists(reportPath):
        alreadyReported = {'num_experiments': 0,
                           'experiments': []}
    else:
        with open(reportPath, 'r') as fr:
            alreadyReported = json.load(fr)
    alreadyReported['num_experiments'] = alreadyReported['num_experiments'] + 1
    experiments = alreadyReported['experiments']
    experiments.append(info)
    alreadyReported['experiments'] = experiments
    with open(reportPath, 'w') as fw:
        json.dump(alreadyReported, fw)


def processTransformersLog(log_history: list) -> Tuple[dict, dict]:
    """
    This function preprocess the log history from transformers before reporting.
    The type of the log_history is always list. The items from 1 to N-1 are evaluation results.
    ... and the last item is a training summary.
    The keys in evaluation results are: eval_loss, eval_accuracy, eval_runtime, eval_samples_per_second, epoch, step
    ... and the keys in training summary are: train_runtime, train_samples_per_second, total_flos, epoch, step

    Args:
        log_history (list): The training log returned by transformers.trainer.state.log_history

    Returns:
        Tuple[dict, dict]: the last evaluation log, and the training summary
    """
    last_eval_state = log_history[-2]
    training_state = log_history[-1]
    return last_eval_state, training_state


def launchExperimentFromDict(d: dict, reportPath: str = './report.json'):
    """ This function launches experiment from a dictionary.

    Args:
        d (dict): [description]
        reportPath (str, optional): The json file to write or append the report. to. Defaults to './report.json'.
    """
    model = ModelConstruction  # default model which does nothing

    # check if model type is of type transformers
    # if ModelType gets more than 3 types this should be changed
    # to a larger match case
    if d['model_type'] == ModelType.transformers.value:
        # TODO: transformers model is used, but a general model is needed here
        model_name_or_path = d['model_name_or_path']
        model = TransformersModel(modelName_or_pipeLine=model_name_or_path)

    if type(d['metric']) is str:
        d['metric'] = [d['metric']]
    assert (d['metric'][0] in list_metrics()), \
        f"The metric for evaluation is not supported.\n" \
        f"It should be in https://huggingface.co/metrics"

    model.registerMetric(*d['metric'])

    model.loadData(ratio=d['data_load_ratio'])

    hyperoptActive = d.get('use_hyperopt', False)
    if not hyperoptActive:
        _ = model.trainModel(
            train_val_split_iterator=d['args'].pop('train_val_split_iterator', "train_test_split"),
            model_config=d['model_config'],
            tokenizer_config=d['tokenizer_config'],
            trainer_config=d['args'],
            freeze_model=False
        )
        best_model_metric = model.getBestMetric()

        report(info={**d,
                     "results": {d['args']['metric_for_best_model']: best_model_metric},
                     "output_dir": f'./results/{model._modelName}',  # for server make this absolute server
                     "time_stamp": dt.datetime.now()},
               reportPath=reportPath)
    else:
        # if use_hyperopt = True inside the dictionary
        # prepare hyperopt to run for various values
        # search for values having this dictionary structure:
        # {"use_hyperopt" , "hyperopt_function", "arguments"}
        # see robertaHyperopt.json for more details.
        space = {argName: getHyperoptValue(argName, argValue)
                 for argName, argValue in d['args'].items()}

        def getEvalsError(args):
            # find which arguments use hyperopt
            # and stop them from being a dictionary
            actualArgs = {}
            for argName, argVal in args.items():
                if type(d['args'][argName]) is dict:
                    if d['args'][argName].get("use_hyperopt", False):
                        actualArgs[argName] = argVal[argName]
                    else:
                        actualArgs[argName] = argVal
                else:
                    actualArgs[argName] = argVal
            # test the model
            # and get evaluations
            evals = model.trainModel(**actualArgs)
            res = 100 - np.sum(evals) / np.size(evals)
            return res

        bestHyperparametersDict = hyperopt.fmin(getEvalsError, space, hyperopt.tpe.suggest,
                                                max_evals=d['hyperopt_max_evals'])
        report(info={**bestHyperparametersDict,
                     "results": evals,
                     "output_dir": f'./results/{model._modelName}',  # for server make this absolute server
                     "time_stamp": dt.datetime.now()},
               reportPath=reportPath)


def getHypervisorFunction(funcName: str) -> callable:
    d = {
        "normal": hyperopt.hp.normal,
        "lognormal": hyperopt.hp.lognormal,
        "loguniform": hyperopt.hp.loguniform,
        "qlognormal": hyperopt.hp.qlognormal,
        "qnormal": hyperopt.hp.qnormal,
        "randint": hyperopt.hp.randint,
        "uniform": hyperopt.hp.uniform,
        "uniformint": hyperopt.hp.uniformint,
        "choice": hyperopt.hp.choice,
        "pchoice": hyperopt.hp.pchoice
    }
    assert (funcName in d.keys()), f"{funcName} not in supported hp functions"
    return d.get(funcName)


def getHyperoptValue(name: str, val: any):
    USE_HYPEROPT = "use_hyperopt"
    HYPEROPT_FUNC = "hyperopt_function"
    HYPEROPT_ARGS = "arguments"
    if type(val) is dict:
        answers = [k in val.keys() for k in [USE_HYPEROPT, HYPEROPT_FUNC, HYPEROPT_ARGS]]
        if np.all(answers):
            # actual hyperopt descriptor
            if val[USE_HYPEROPT]:
                hpfunc = getHypervisorFunction(val[HYPEROPT_FUNC])
                return {name: hpfunc(name, **val[HYPEROPT_ARGS])}
            else:
                print("Error: Having a hyperopt descriptor but hyperopt usage is not active")
                assert (False)
                return {name: ""}
        else:
            # a key-value has been forgotten
            assert not (np.any(answers))
            return val
    else:
        return val


def launchExperimentFromJson(fpath: str, reportPath: str):
    """This launches experiment described in a json file.
    It reads a json file it transforms is to  dict and calls the launchExperimentFromDict
    function.

    Args:
        fpath (str): The path of the json file

    Raises:
        FileNotFoundError: No json found at path if path does not exist
    """
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"No json fount at {fpath}")
    with open(fpath, 'r') as fr:
        experimentSettings = json.load(fr)
        launchExperimentFromDict(experimentSettings, reportPath)


def main(args: list):
    """ The main function of the program. It launches an experiment from a json file specified and reports
    to a file specified, else it reports to ./report.json.
    use args:
    - test_path=<your test path> for setting the path of the test json file
    - report_path=<your report destination path> for setting the path for the report to be written or appended. 
    call it like:
    python experimentConfigs/experiment.py test_path=experimentConfigs/robertaDefault.json report_path=report.json
    Args:
        args (list): a dictionary containing the program arguments (sys.argv)
    """
    argv = {a.split('=')[0]: a.split('=')[1] for a in args[1:]}
    testPath = argv.get('test_path', None)
    reportPath = argv.get('report_path', './report.json')
    if testPath is None:
        print("No test_path specified")
        exit(0)
    launchExperimentFromJson(testPath, reportPath)


if __name__ == "__main__":
    main(sys.argv)
