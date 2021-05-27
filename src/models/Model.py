import abc
import typing
import numpy as np
import sklearn
from sklearn import model_selection
ModelConstruction = object


class TrainTestSplit:
    def split(self, X:list, y=None, test_size:float=0.1) -> typing.Tuple[np.ndarray,np.ndarray]:
        xLen = len(X)
        train_size = int(xLen*(1-test_size))
        train_index = np.random.choice(range(xLen), size=train_size)
        test_index = np.array([i for i in range(xLen) if not i in train_index])
        yield (train_index, test_index)      

def get_iterator_splitter_from_name(it_name: str):
    return {
        "train_test_split": TrainTestSplit,
        "cross_val_score": sklearn.model_selection.cross_val_score,
        "cross_validate_accuracy": lambda clf,X,y: sklearn.model_selection.cross_validate(clf, X, y, scoring=['accuracy']),
        "stratifiedKfold": sklearn.model_selection.StratifiedKFold(n_splits=10)
    }[it_name]