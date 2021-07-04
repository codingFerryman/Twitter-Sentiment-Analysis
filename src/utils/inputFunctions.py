import random
from pathlib import PurePath
from typing import Union, Tuple

import numpy as np

from utils.loggers import getLogger
from utils.utils import get_data_path

DATA_DIRECTORY = get_data_path()
logger = getLogger("InputPipeline", debug=True)


def loadData(dataDirectory: str = None, ratio: Union[str, float, int] = None) -> Tuple[list, list, list]:
    """
    Load datasets
    Args:
        dataDirectory (str or pathlib.Path):
        ratio: "sub", "full"; Or a float number between 0 and 1, which is the proportion of the full set

    Returns:
        3 lists: Positive training set, Negative training set and Test set
    """
    if dataDirectory is None:
        dataDirectory = DATA_DIRECTORY
    if ratio is None:
        ratio = "sub"
    with open(PurePath(dataDirectory, 'train_pos.txt'), 'r', encoding='utf-8') as fp:
        train_pos_sub = fp.readlines()
    with open(PurePath(dataDirectory, 'train_neg.txt'), 'r', encoding='utf-8') as fp:
        train_neg_sub = fp.readlines()
    with open(PurePath(dataDirectory, 'train_pos_full.txt'), 'r', encoding='utf-8') as fp:
        train_pos_full = fp.readlines()
    with open(PurePath(dataDirectory, 'train_neg_full.txt'), 'r', encoding='utf-8') as fp:
        train_neg_full = fp.readlines()
    with open(PurePath(dataDirectory, 'test_data.txt'), 'r', encoding='utf-8') as fp:
        test_full = fp.readlines()

    if type(ratio) is int:
        ratio = float(ratio)
    assert isinstance(ratio, str) or isinstance(ratio, float)
    if type(ratio) is float:
        if ratio <= 0 or ratio > 1:
            raise AttributeError('The input should be \'full\', \'sub\', or a (float) number between 0 and 1')
        num_samples = int(ratio * len(train_pos_full))
        pos = random.sample(train_pos_full, num_samples)
        neg = random.sample(train_neg_full, num_samples)
    else:
        if ratio == 'full':
            pos = train_pos_full
            neg = train_neg_full
        elif ratio == 'sub':
            pos = train_pos_sub
            neg = train_neg_sub
        else:
            raise AttributeError('The input should be \'full\', \'sub\', or a (float) number between 0 and 1')
    logger.info(f"Dataset loaded!")
    logger.debug(f"Positive: {len(pos)}, Negative: {len(neg)}, Test: {len(test_full)}")
    return pos, neg, test_full


def loadDataForUnitTesting(dataDirectory: str = None, ratio: float = 0.0002) -> Tuple[list, list, list]:
    return loadData(dataDirectory, ratio)


def randomizeData(train_pos: list, train_neg: list) -> Tuple[np.ndarray, np.ndarray]:
    res_pos = np.random.shuffle(train_pos)
    res_neg = np.random.shuffle(train_neg)
    return res_pos, res_neg