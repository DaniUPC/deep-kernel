
from protodata import datasets
from protodata.utils import get_data_location
import sys
import shutil
import logging
import os

from layout import kernel_example_layout_fn
from training.fit_validate import DeepNetworkValidation
from training.fit import DeepNetworkTraining


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s %(message)s',
)

logger = logging.getLogger(__name__)


if __name__ == '__main__':

    fit = bool(int(sys.argv[1]))
    folder = '/media/walle/815d08cd-6bee-4a13-b6fd-87ebc1de2bb01/walle/aus'

    params = {
        'l2_ratio': 1e-3,
        'lr': 1e-4,
        'lr_decay': 0.5,
        'lr_decay_epocs': 500,
        'memory_factor': 2,
        'hidden_units': 512,
        'n_threads': 4,
        'kernel_size': 512,
        'kernel_mean': 0.0,
        'kernel_std': 0.25,
        'strip_length': 5,
        'batch_size': 128,
        'num_layers': 4,
        'max_epochs': 20,
        'network_fn': kernel_example_layout_fn
    }

    settings = datasets.MagicSettings
    dataset = datasets.Datasets.MAGIC

    if fit:

        if os.path.isdir(folder):
            shutil.rmtree(folder)

        '''
        m = DeepNetworkTraining(
            folder=folder,
            settings_fn=settings,
            data_location=get_data_location(dataset, folded=True)
        )

        m.fit(
            # starting_layer=1,
            # switch_epochs=[(50, 2), (200, 3), (400, 4)],
            **params
        )
        '''

        m = DeepNetworkValidation(
            folder=folder,
            settings_fn=settings,
            data_location=get_data_location(dataset, folded=True)
        )
        m.fit(train_folds=range(9), val_folds=[9], layerwise=False, **params)

    else:

        res = m.predict(
            data_settings_fn=settings,
            folder=folder,
            data_location=get_data_location(dataset, folded=True),
            **params
        )

        logger.info('Got results {} for prediction'.format(res))
