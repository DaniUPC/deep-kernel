from hyperopt import hp
from protodata.datasets import Datasets, TitanicSettings
from cross_validation import evaluate_model

CV_TRIALS = 1
SIM_RUNS = 10


if __name__ == '__main__':

    search_space = {
        'batch_size': hp.choice('batch_size', [32, 64, 128]),
        # l1 ratio not present in paper
        'l2_ratio': hp.choice('l2_ratio', [0, 1e-1, 1e-2, 1e-3]),
        'lr': hp.choice('lr', [1e-1, 1e-2, 1e-3]),
        'hidden_units': hp.choice('hidden_units', [64, 128, 256])
    }

    # Fixed parameters
    search_space.update({
        'n_threads': 2,
        'memory_factor': 2,
        'validation_interval': 250,
        'max_steps': 50000,
        'train_tolerance': 1e-3
    })

    evaluate_model(
        Datasets.TITANIC,
        TitanicSettings,
        search_space,
        '/media/walle/815d08cd-6bee-4a13-b6fd-87ebc1de2bb0/walle/ev',
        cv_trials=CV_TRIALS,
        runs=SIM_RUNS
    )
