import tensorflow as tf
import os
import logging
import numpy as np

from training import create_global_step, save_model, get_writer, \
    eval_epoch, progress, run_training_epoch, init_kernel_ops, \
    build_run_context

from protodata.data_ops import DataMode
from protodata.reading_ops import DataReader

logger = logging.getLogger(__name__)

# TODO: switch Monitored Session by custom

# Disable Tensorflow debug messages
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'


class DeepKernelModel():

    """ Class that combines fully connected and kernel functions """

    def __init__(self, verbose=True):
        self._verbose = verbose
        self._layer_idx = None
        self._epochs = None

    def fit(self, **params):

        # Mandatory parameters
        max_epochs = int(params.get('max_epochs'))
        data_settings_fn = params.get('data_settings_fn')
        data_location = params.get('data_location')

        # Parameters with default values
        folder = params.get('folder')
        switch_epochs = params.get('switch_epochs', None).copy()
        is_layerwise = switch_epochs is not None
        summary_epochs = params.get('summary_epochs', 1)

        with tf.Graph().as_default() as graph:

            step = create_global_step()

            dataset = data_settings_fn(dataset_location=data_location)
            reader = DataReader(dataset)

            # Get training operations
            train_flds = range(dataset.get_fold_num())
            train_context = build_run_context(
                dataset, reader, DataMode.TRAINING, train_flds, step, **params
            )

            # Initialize writers and summaries
            writer = tf.summary.FileWriter(folder, graph)
            summary_op = tf.summary.merge_all(DataMode.TRAINING)
            saver = tf.train.Saver()

            self._initialize_training(is_layerwise)

            with tf.train.MonitoredTrainingSession(
                    save_checkpoint_secs=None,
                    save_summaries_steps=None,
                    save_summaries_secs=None) as sess:

                init_kernel_ops(sess)

                # Define coordinator to handle all threads
                coord = tf.train.Coordinator()
                threads = tf.train.start_queue_runners(coord=coord, sess=sess)

                for epoch in range(max_epochs):

                    loss_mean, acc_mean = run_training_epoch(
                        sess, train_context, self._layer_idx
                    )

                    if epoch % summary_epochs == 0:
                        # Store training summaries
                        sum_str = sess.run(summary_op)
                        writer.add_summary(sum_str, epoch)

                        self.log_info(
                            '[%d] Training Loss: %f, Error: %f'
                            % (epoch, loss_mean, 1-acc_mean)
                        )

                    if switch_epochs is not None and len(switch_epochs) > 0 \
                            and epoch == switch_epochs[0]:
                        self._iterate_layer(epoch, [1-acc_mean], **params)
                        switch_epochs = switch_epochs[1:]

                self.log_info('Finished training at step %d' % max_epochs)
                model_path = save_model(sess, saver, folder, max_epochs)

                coord.request_stop()
                coord.join(threads)

        return model_path

    def fit_and_validate(self, **params):

        # Mandatory parameters
        train_flds = params.get('training_folds')
        val_folds = params.get('validation_folds')
        max_epochs = int(params.get('max_epochs'))
        data_settings_fn = params.get('data_settings_fn')
        data_location = params.get('data_location')

        # Parameters with default values
        folder = params.get('folder', None)
        should_save = folder is not None
        summary_epochs = params.get('summary_epochs', 1)
        strip_length = params.get('strip_length', 5)
        progress_thresh = params.get('progress_thresh', 0.1)
        max_successive_strips = params.get('max_successive_strips', 3)
        is_layerwise = params.get('layerwise', False)

        best_model = {'val_error': float('inf')}
        prev_val_err = float('inf')
        successive_fails = 0

        self._initialize_training(is_layerwise)

        with tf.Graph().as_default() as graph:

            step = create_global_step()

            dataset = data_settings_fn(dataset_location=data_location)
            reader = DataReader(dataset)

            # Get training operations
            train_context = build_run_context(
                dataset, reader, DataMode.TRAINING, train_flds, step, **params
            )

            # Get validation operations
            val_context = build_run_context(
                dataset, reader, DataMode.VALIDATION, val_folds, step, True, **params  # noqa
            )

            if should_save:
                # Initialize writers
                train_writer = get_writer(graph, folder, DataMode.TRAINING)

                val_writer_path = os.path.join(folder, DataMode.VALIDATION)
                os.makedirs(val_writer_path)
                val_writer = tf.summary.FileWriter(val_writer_path, graph)

            # Gather summaries by dataset
            train_summary_op = tf.summary.merge_all(DataMode.TRAINING)
            val_summary_op = tf.summary.merge_all(DataMode.VALIDATION)

            train_losses, train_errors = [], []

            if should_save:
                saver = tf.train.Saver()

            with tf.train.MonitoredTrainingSession(
                    save_checkpoint_secs=None,
                    save_summaries_steps=None,
                    save_summaries_secs=None) as sess:

                init_kernel_ops(sess)

                # Define coordinator to handle all threads
                coord = tf.train.Coordinator()
                threads = tf.train.start_queue_runners(coord=coord, sess=sess)

                for epoch in range(max_epochs):

                    epoch_loss, epoch_acc = run_training_epoch(
                        sess, train_context, self._layer_idx
                    )
                    train_losses.append(epoch_loss)
                    train_errors.append(1-epoch_acc)

                    if should_save and epoch % summary_epochs == 0:
                        # Store training summaries for current
                        sum_str = sess.run(train_summary_op)
                        sum_str_val = sess.run(val_summary_op)
                        train_writer.add_summary(sum_str, epoch)
                        val_writer.add_summary(sum_str_val, epoch)

                    if epoch % strip_length == 0 and epoch != 0:

                        stop = False

                        # Track training loss and restart values
                        self.log_info(
                            '[%d] Training Loss: %f, Error: %f'
                            % (epoch, epoch_loss, 1 - epoch_acc)
                        )

                        # Track validation loss
                        mean_val_loss, mean_val_acc = eval_epoch(
                            sess, val_context, self._layer_idx
                        )
                        self.log_info(
                            '[%d] Validation loss: %f, Error: %f'
                            % (epoch, mean_val_loss, 1 - mean_val_acc)
                        )

                        # Track best model at validation
                        if best_model['val_error'] > (1 - mean_val_acc):
                            self.log_info('[%d] New best found' % epoch)

                            if should_save:
                                save_model(
                                    sess, saver, folder, epoch
                                )

                            best_model = {
                                'val_loss': mean_val_loss,
                                'val_error': 1 - mean_val_acc,
                                'epoch': epoch,
                                'train_loss': epoch_loss,
                                'train_error': 1 - epoch_acc,
                            }

                        # Stop using progress criteria
                        train_progress = progress(train_errors)
                        if train_progress < progress_thresh:
                            self.log_info(
                                '[%d] Stuck in training due to ' % epoch +
                                'lack of progress (%f < %f). Halting...'
                                % (train_progress, progress_thresh)
                            )
                            stop = True

                        # Stop using UP criteria
                        if prev_val_err < (1 - mean_val_acc):
                            successive_fails += 1
                            self.log_info(
                                '[%d] Validation error increases. ' % epoch +
                                'Successive fails: %d' % successive_fails
                            )
                        else:
                            successive_fails = 0

                        if successive_fails == max_successive_strips:
                            self.log_info(
                                '[%d] Validation error increased ' % epoch +
                                'for %d successive ' % max_successive_strips +
                                'times. Halting ...'
                            )
                            stop = True

                        if stop and is_layerwise:
                            self._iterate_layer(
                                epoch, train_errors, **params
                            )

                            successive_fails = 0
                            if self._layerwise_stop(1-mean_val_acc, **params):
                                break
                        elif stop and not is_layerwise:
                            break

                        prev_val_err = 1 - mean_val_acc
                        train_losses, train_errors = [], []

                self.log_info('Best model found: {}'.format(best_model))

                coord.request_stop()
                coord.join(threads)

        return best_model

    def predict(self, X=None, y=None, **params):

        data_settings_fn = params.get('data_settings_fn')
        data_location = params.get('data_location')
        folder = params.get('folder')
        store_summaries = params.get('summaries', True)

        with tf.Graph().as_default() as graph:

            step = create_global_step()

            dataset = data_settings_fn(dataset_location=data_location)
            reader = DataReader(dataset)

            # Get training operations
            test_context = build_run_context(
                dataset=dataset, reader=reader, tag=DataMode.TEST,
                folds=None, step=step, is_training=False, **params
            )

            if store_summaries:
                writer = get_writer(graph, folder, DataMode.TEST)
            summary_op = tf.summary.merge_all(DataMode.TEST)

            saver = tf.train.Saver()

            with tf.train.MonitoredTrainingSession(
                    save_checkpoint_secs=None,
                    save_summaries_steps=None,
                    save_summaries_secs=None) as sess:

                ckpt = tf.train.get_checkpoint_state(folder)
                if ckpt and ckpt.model_checkpoint_path:
                    # Restores from checkpoint
                    saver.restore(sess, ckpt.model_checkpoint_path)
                else:
                    raise ValueError('No model found in %s' % folder)

                # Define coordinator to handle all threads
                coord = tf.train.Coordinator()
                threads = tf.train.start_queue_runners(coord=coord, sess=sess)

                losses, accs, finish = [], [], False

                while not finish:

                    try:
                        # Track loss and accuracy until queue exhausted
                        loss, acc, summary = sess.run(
                            [
                                test_context.loss_ops[0],  # Use all layers
                                test_context.acc_op,
                                summary_op
                            ]
                        )
                        losses.append(loss)
                        accs.append(acc)

                        if store_summaries:
                            writer.add_summary(summary)

                    except tf.errors.OutOfRangeError:
                        logger.info('Queue exhausted. Read all instances')
                        finish = True

                coord.request_stop()
                coord.join(threads)

        return {'loss': np.mean(losses), 'error': 1 - np.mean(accs)}

    def log_info(self, msg):
        if self._verbose:
            logger.info(msg)

    def _initialize_training(self, layerwise):
        if layerwise:
            self._layer_idx = 1
            self._epochs = []
            self._train_errors = []
            self._prev_val_error = float('inf')
        else:
            self._layer_idx = 0

    def _iterate_layer(self, epoch, train_errors, **params):
        layers = params.get('num_layers')
        self._layer_idx = max(((self._layer_idx + 1) % (layers + 1)), 1)
        self._epochs.append(epoch)
        self._train_errors.append(np.mean(train_errors))
        self.log_info('Switching to layer %d' % self._layer_idx)

    def _layerwise_stop(self, val_error, **params):
        if self._layer_idx == 1:
            # Evaluate only when a complete cycle finished
            thresh = params.get('layerwise_progress_thresh', 0.1)
            if progress(self._train_errors) < thresh:
                self.log_info(
                    'Stopping layerwise cyclying due to lack of progress.'
                )
                return True
            elif self._prev_val_error < val_error:
                self.log_info(
                    'Stopping layerwise cyclying: validation error increase' +
                    '. Had %f, now %f.' % (self._prev_val_error, val_error))
                return True

            self._prev_val_error = val_error
            self._train_errors = []
            return False
        else:
            return False


from protodata import datasets
from protodata.utils import get_data_location
import sys
import shutil

if __name__ == '__main__':

    fit = bool(int(sys.argv[1]))
    folder = 'aus'

    params = {
        'l2_ratio': 1e-2,
        'lr': 1e-3,
        'lr_decay': 0.5,
        'lr_decay_epocs': 400,
        'memory_factor': 2,
        'hidden_units': 128,
        'n_threads': 4,
        'kernel_size': 128,
        'kernel_mean': 0.0,
        'kernel_std': 0.1,
        'strip_length': 2,
        'batch_size': 16,
        'num_layers': 3,
        'max_epochs': 60
    }

    m = DeepKernelModel(verbose=True)

    if fit:

        if os.path.isdir(folder):
            shutil.rmtree(folder)           

        '''
        m.fit_and_validate(
            data_settings_fn=datasets.AusSettings,
            training_folds=range(9),
            validation_folds=[9],
            layerwise=True,
            data_location=get_data_location(datasets.Datasets.AUS, folded=True),  # noqa
            folder=folder,
            **params
        )
        '''

        m.fit(
            data_settings_fn=datasets.AusSettings,
            training_folds=range(9),
            validation_folds=[9],
            switch_epochs=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 140],
            data_location=get_data_location(datasets.Datasets.AUS, folded=True),  # noqa
            folder=folder,
            **params
        )

    else:

        res = m.predict(
            data_settings_fn=datasets.AusSettings,
            folder=folder,
            data_location=get_data_location(datasets.Datasets.AUS, folded=True),  # noqa
            **params
        )

        print('Got results {} for prediction'.format(res))
