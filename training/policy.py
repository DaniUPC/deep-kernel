import numpy as np
import abc


class LayerPolicy(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, num_layers):
        self._num_layers = num_layers
        self._layer_id = self.initial_layer_id()

    @abc.abstractmethod
    def name(self):
        """
        Returns the policy string identifier
        """

    @abc.abstractmethod
    def initial_layer_id(self):
        """
        Returns the identifier of the first later to train
        """

    @abc.abstractmethod
    def next_layer_id(self):
        """
        Returns the id of next layer to train
        """

    @abc.abstractmethod
    def cycle_ended(self):
        """
        Whether the current layer is the beginning of a new cycle
        """


class CyclicPolicy(LayerPolicy):

    def initial_layer_id(self):
        return 1

    def next_layer_id(self):
        next_layer = (self._layer_id + 1) % (self._num_layers + 1)
        self._layer_id = max(next_layer, 1)
        return self._layer_id

    def cycle_ended(self):
        return self._layer_id == 1

    def name(self):
        return 'cyclic'


class InverseCyclingPolicy(LayerPolicy):

    def initial_layer_id(self):
        return self._num_layers

    def next_layer_id(self):
        self._layer_id = self._num_layers \
            if self._layer_id == 1 else self._layer_id - 1
        return self._layer_id

    def cycle_ended(self):
        return self._layer_id == self._num_layers

    def name(self):
        return 'inv_cyclic'


class RandomPolicy(LayerPolicy):

    def __init__(self, num_layers):
        super(RandomPolicy, self).__init__(num_layers)
        self._count = 0

    def initial_layer_id(self):
        return self._num_layers

    def next_layer_id(self):
        self._count = (self._count + 1) % self._num_layers
        self._layer_id = np.random.randint(1, self._num_layers+1)
        return self._layer_id

    def cycle_ended(self):
        return self._count == 0

    def name(self):
        return 'random'
