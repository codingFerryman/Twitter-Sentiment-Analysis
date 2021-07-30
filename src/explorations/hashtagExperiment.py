import json
import os
import sys
from pathlib import Path

import pandas as pd
import torch
from sklearn.metrics import accuracy_score
from tqdm.auto import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from utils import get_project_path, loggers

logger = loggers.getLogger('HashtagExperiment', debug=1)

PROJECT_DIRECTORY = get_project_path()

def load_hashtag_config():
    # Load hashtag frequency data
    # ... this file was generated by explorations/Data_Exploration.ipynb
    with open(Path(PROJECT_DIRECTORY, 'src', 'models/hashtag.json'), 'r') as fp:
        hashtag_dict = json.load(fp)
    return hashtag_dict

def extract_hashtag_dataset(model_path, data_path=None, prediction_path=None):
    """Extract hashtag-only tweets and join their golden labels with predictions"""
    df_data_path = Path(model_path, "hashtag_data.pkl")
    if df_data_path.is_file():
        logger.info(f"Loading the data from {df_data_path}")
        df_data = pd.read_pickle(df_data_path)
    else:
        with open(data_path, 'r') as fp:
            data_t = fp.readlines()

        logger.info("Loading predictions ...")
        df_p = pd.read_csv(prediction_path,
                           names=['id', 'prediction', 'score'],
                           dtype={'id': int, 'prediction': int, 'score': float},
                           delimiter=',',
                           header=None,
                           skiprows=1,
                           index_col='id')

        # read_csv in Pandas 1.3.x we are using has bugs in this experiment
        logger.info("Loading dataset ...")
        df_t = pd.DataFrame(columns=['id', 'golden', 'text'])
        for _t in tqdm(data_t, mininterval=5, dynamic_ncols=True, maxinterval=15):
            _tmp = _t.split('\u0001', 2)
            _id = int(_tmp[0])
            _golden = int(_tmp[1])
            _text = _tmp[2]
            for _w in _text.split():
                if _w.startswith('#') and len(_w) > 1:
                    to_append = [_id, _golden, _text]
                    to_append_series = pd.Series(to_append, index=df_t.columns)
                    df_t = df_t.append(to_append_series, ignore_index=True)
                    break

        df_data = df_t.join(df_p, on="id").set_index("id")
        logger.info(f"Saving the data to {df_data_path}")
        df_data.to_pickle(df_data_path)
    return df_data


def predict_by_hashtag(text: str,
                       pred_pos_prob: float, pred_neg_prob: float,
                       freq_threshold: float, prob_threshold: float):
    hashtag_dict = load_hashtag_config()
    for _w in text.split():
        if _w.startswith('#') and len(_w) > 1:
            if _w[1:] in hashtag_dict.keys():
                tag = _w[1:]
                neg_freq = hashtag_dict[tag]['NegFreq']
                pos_freq = hashtag_dict[tag]['PosFreq']
                neg_ratio = hashtag_dict[tag]['NegRatio']
                pos_ratio = hashtag_dict[tag]['PosRatio']
                if (pos_freq > freq_threshold or neg_freq > freq_threshold) and (
                        neg_ratio > prob_threshold or pos_ratio > prob_threshold):
                    pred_neg_prob += neg_ratio
                    pred_pos_prob += pos_ratio
    _pred_prob = torch.softmax(torch.tensor([pred_neg_prob, pred_pos_prob]), dim=-1)
    _pred = torch.argmax(_pred_prob, dim=-1).item()
    if _pred == 0:
        _pred = -1
    return _pred


def _hashtag_matters(data_line: pd.Series, **kwargs):
    row = data_line
    _text = row['text']
    _prediction = row['prediction']
    if '#' in _text:
        _score = row['score']
        if _prediction == 1:
            _pos_prob = _score
            _neg_prob = 1 - _score
        else:
            _pos_prob = 1 - _score
            _neg_prob = _score
        _pred = predict_by_hashtag(text=_text, pred_pos_prob=_pos_prob, pred_neg_prob=_neg_prob, **kwargs)
    else:
        _pred = _prediction
    return _pred


def hashtag_matters(data: pd.DataFrame, **kwargs):
    tqdm.pandas(desc="Hashtag analyzing: ")
    data['new_prediction'] = data.progress_apply(lambda row: _hashtag_matters(row, **kwargs), axis=1)
    return data


def main(args: list):
    """
    The function for analysis the impact of hashtags in tweet sentiment analysis.
    The dataset used here should be preprocessed by explorations/evaluate_trainset.py beforehand
    ... after preprocessing, the dataset and the predictions will be available.
    Args:
        args:
            - dataset: "full" or "sub"
            - load_path: The directory of prediction file.
            - freq: The frequency threshold. Hashtags with lower frequency will be ignored.
            - prob: The probability/ratio threshold. Hashtags with lower probability/ratio will be ignored.
    """
    argv = {a.split('=')[0]: a.split('=')[1] for a in args[1:]}

    dataset_file = argv.get('dataset', 'full')
    load_path = argv.get('load_path', None)
    _load_path_for_test = Path(PROJECT_DIRECTORY, 'trainings/vinai/bertweet-base/20210711-131720')
    if load_path is None:
        if _load_path_for_test.is_dir():
            load_path = _load_path_for_test
        else:
            print("No load_path specified")
            exit(0)
    PREDICTION_FILE = Path(load_path, 'pred_train_' + dataset_file + '.csv')
    DATA_FILE = Path(PROJECT_DIRECTORY, 'data/' + dataset_file + '_data.txt')

    freq_threshold = argv.get("freq", 100)
    prob_threshold = argv.get("prob", 0.6)

    logger.info(f"The frequency and ratio thresholds are set to {freq_threshold}, and {prob_threshold} respectively.")

    df_data = extract_hashtag_dataset(model_path=load_path, data_path=DATA_FILE, prediction_path=PREDICTION_FILE)

    original_accuracy = accuracy_score(df_data.prediction.tolist(), df_data.golden.tolist())
    logger.info(f"The accuracy before processing is {original_accuracy}")

    df_data = hashtag_matters(df_data, freq_threshold=freq_threshold, prob_threshold=prob_threshold)

    accuracy = accuracy_score(df_data.new_prediction.tolist(), df_data.golden.tolist())
    logger.info(f"The accuracy after processing is {accuracy}")


if __name__ == '__main__':
    main(sys.argv)
